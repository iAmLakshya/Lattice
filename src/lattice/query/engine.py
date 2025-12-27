import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from lattice.config import get_settings
from lattice.core.errors import QueryError
from lattice.embeddings.client import CollectionName, QdrantManager
from lattice.embeddings.embedder import OpenAIEmbedder
from lattice.graph.client import MemgraphClient
from lattice.query.context import ContextBuilder, EnrichedContext, format_context_for_llm
from lattice.query.graph_reasoning import GraphContext, GraphReasoningEngine
from lattice.query.query_planner import QueryIntent, QueryPlan, QueryPlanner
from lattice.query.ranking import HybridRanker, RankedResult, RankingConfig
from lattice.query.responder import ResponseGenerator
from lattice.query.vector_search import VectorSearcher

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    answer: str
    sources: list[RankedResult]
    query_plan: QueryPlan
    context: EnrichedContext
    graph_context: GraphContext
    execution_stats: dict[str, Any]


class QueryEngine:
    """Hybrid query engine combining graph reasoning and vector search."""

    def __init__(
        self,
        memgraph: MemgraphClient | None = None,
        qdrant: QdrantManager | None = None,
        embedder: OpenAIEmbedder | None = None,
        planner: QueryPlanner | None = None,
        graph_engine: GraphReasoningEngine | None = None,
        vector_searcher: VectorSearcher | None = None,
        context_builder: ContextBuilder | None = None,
        ranker: HybridRanker | None = None,
        responder: ResponseGenerator | None = None,
    ):
        self._memgraph = memgraph
        self._qdrant = qdrant
        self._embedder = embedder
        self._planner = planner
        self._graph_engine = graph_engine
        self._vector_searcher = vector_searcher
        self._context_builder = context_builder
        self._ranker = ranker or HybridRanker(RankingConfig())
        self._responder = responder
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("Initializing query engine")

        if self._memgraph is None:
            self._memgraph = MemgraphClient()
            await self._memgraph.connect()

        if self._qdrant is None:
            self._qdrant = QdrantManager()
            await self._qdrant.connect()

        if self._embedder is None:
            self._embedder = OpenAIEmbedder()

        if self._planner is None:
            self._planner = QueryPlanner()

        if self._graph_engine is None:
            self._graph_engine = GraphReasoningEngine(self._memgraph)

        if self._vector_searcher is None:
            self._vector_searcher = VectorSearcher(self._qdrant, self._embedder)

        if self._context_builder is None:
            self._context_builder = ContextBuilder(self._memgraph, self._qdrant)

        if self._responder is None:
            self._responder = ResponseGenerator()

        self._initialized = True
        logger.info("Query engine initialized")

    async def close(self) -> None:
        logger.info("Closing query engine")

        if self._memgraph:
            await self._memgraph.close()
        if self._qdrant:
            await self._qdrant.close()

        self._initialized = False

    async def query(
        self,
        question: str,
        limit: int | None = None,
        language: str | None = None,
        use_llm_planning: bool = True,
        project_name: str | None = None,
    ) -> QueryResult:
        await self.initialize()
        settings = get_settings()
        limit = limit or settings.query.search_limit

        stats = {
            "planning_time_ms": 0,
            "graph_time_ms": 0,
            "vector_time_ms": 0,
            "ranking_time_ms": 0,
            "context_time_ms": 0,
            "response_time_ms": 0,
        }

        try:
            logger.info(f"Executing query: {question}")

            import time
            start = time.time()

            if use_llm_planning:
                plan = await self._planner.plan_query(question)
            else:
                plan = self._planner._fallback_plan(question)

            stats["planning_time_ms"] = int((time.time() - start) * 1000)
            logger.debug(f"Query plan: intent={plan.primary_intent}, entities={len(plan.entities)}")

            start = time.time()

            graph_task = self._graph_engine.execute_query_plan(plan)
            vector_task = self._execute_vector_search(question, plan, limit, language, project_name)

            graph_context, vector_results = await asyncio.gather(
                graph_task,
                vector_task,
                return_exceptions=True,
            )

            stats["graph_time_ms"] = int((time.time() - start) * 1000)

            if isinstance(graph_context, Exception):
                logger.warning(f"Graph search failed: {graph_context}")
                graph_context = GraphContext(
                    primary_entities=[],
                    callers=[],
                    callees=[],
                    parent_classes=[],
                    child_classes=[],
                    methods=[],
                    containing_class=None,
                    file_context=[],
                    dependencies=[],
                    dependents=[],
                    call_chains=[],
                    inheritance_chains=[],
                )

            if isinstance(vector_results, Exception):
                logger.warning(f"Vector search failed: {vector_results}")
                vector_results = []

            start = time.time()
            centrality_scores = await self._get_centrality_scores(graph_context, vector_results)
            stats["vector_time_ms"] = int((time.time() - start) * 1000)

            start = time.time()
            ranked_results = self._ranker.rank_results(
                plan,
                graph_context,
                vector_results,
                centrality_scores,
            )
            stats["ranking_time_ms"] = int((time.time() - start) * 1000)

            start = time.time()
            enriched_context = await self._context_builder.build_enriched_context(
                plan,
                graph_context,
                vector_results,
            )
            stats["context_time_ms"] = int((time.time() - start) * 1000)

            start = time.time()
            answer = await self._generate_enhanced_response(
                question,
                plan,
                ranked_results[:limit],
                enriched_context,
            )
            stats["response_time_ms"] = int((time.time() - start) * 1000)

            total_time = sum(stats.values())
            logger.info(
                f"Query completed in {total_time}ms: "
                f"{len(ranked_results)} results, intent={plan.primary_intent}"
            )

            return QueryResult(
                answer=answer,
                sources=ranked_results[:limit],
                query_plan=plan,
                context=enriched_context,
                graph_context=graph_context,
                execution_stats=stats,
            )

        except QueryError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during enhanced query: {e}")
            raise QueryError("Query execution failed", cause=e)

    async def search(
        self,
        query: str,
        limit: int | None = None,
        language: str | None = None,
        entity_type: str | None = None,
        project_name: str | None = None,
    ) -> list[RankedResult]:
        await self.initialize()
        settings = get_settings()
        limit = limit or settings.query.search_limit

        try:
            logger.info(f"Executing search: {query}")

            plan = await self._planner.plan_query(query)

            graph_context, vector_results = await asyncio.gather(
                self._graph_engine.execute_query_plan(plan),
                self._execute_vector_search(query, plan, limit * 2, language, project_name),
            )

            centrality_scores = await self._get_centrality_scores(graph_context, vector_results)

            ranked_results = self._ranker.rank_results(
                plan,
                graph_context,
                vector_results,
                centrality_scores,
            )

            logger.info(f"Search completed: {len(ranked_results[:limit])} results")
            return ranked_results[:limit]

        except QueryError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise QueryError("Search execution failed", cause=e)

    async def explain_entity(
        self,
        entity_name: str,
        include_callers: bool = True,
        include_callees: bool = True,
        max_depth: int = 2,
    ) -> QueryResult:
        question = f"Explain how {entity_name} works and is used in the codebase"
        return await self.query(question)

    async def find_call_path(
        self,
        source_name: str,
        target_name: str,
        max_hops: int = 5,
    ) -> QueryResult:
        question = f"How does {source_name} eventually call {target_name}? Show the call chain."
        return await self.query(question)

    async def get_statistics(self) -> dict[str, Any]:
        await self.initialize()

        try:
            graph_stats = await self._memgraph.execute(
                """
                MATCH (f:File)
                WITH count(f) as file_count
                MATCH (c:Class)
                WITH file_count, count(c) as class_count
                MATCH (fn:Function)
                WITH file_count, class_count, count(fn) as function_count
                MATCH (m:Method)
                RETURN file_count, class_count, function_count, count(m) as method_count
                """
            )

            try:
                code_info = await self._qdrant.get_collection_info(
                    CollectionName.CODE_CHUNKS.value
                )
                vector_count = code_info.points_count
            except Exception:
                vector_count = 0

            stats = graph_stats[0] if graph_stats else {}
            stats["vector_count"] = vector_count

            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise QueryError("Failed to get statistics", cause=e)

    async def _execute_vector_search(
        self,
        query: str,
        plan: QueryPlan,
        limit: int,
        language: str | None,
        project_name: str | None = None,
    ) -> list[dict[str, Any]]:
        settings = get_settings()
        max_vector = settings.query.max_vector_results
        code_results = await self._vector_searcher.search_code(
            query=query,
            limit=min(limit, max_vector),
            language=language,
            project_name=project_name,
        )

        if plan.primary_intent in (
            QueryIntent.EXPLAIN_IMPLEMENTATION,
            QueryIntent.EXPLAIN_RELATIONSHIP,
            QueryIntent.EXPLAIN_DATA_FLOW,
            QueryIntent.EXPLAIN_ARCHITECTURE,
            QueryIntent.SEARCH_FUNCTIONALITY,
        ):
            summary_results = await self._vector_searcher.search_summaries(
                query=query,
                limit=limit // 2,
                project_name=project_name,
            )
            code_results.extend(summary_results)

        return code_results

    async def _get_centrality_scores(
        self,
        graph_context: GraphContext,
        vector_results: list[dict[str, Any]],
    ) -> dict[str, dict[str, int]]:
        entities = set()

        for entity in graph_context.primary_entities[:5]:
            entities.add(entity.qualified_name or entity.name)

        for vr in vector_results[:5]:
            if vr.get("entity_name"):
                entities.add(vr.get("graph_node_id") or vr.get("entity_name"))

        settings = get_settings()
        entities = list(entities)[:settings.query.max_centrality_lookups]

        scores = {}
        if entities:
            tasks = [
                self._graph_engine.get_entity_centrality(name)
                for name in entities
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(entities, results):
                if isinstance(result, dict):
                    scores[name] = result

        return scores

    async def _generate_enhanced_response(
        self,
        question: str,
        plan: QueryPlan,
        results: list[RankedResult],
        context: EnrichedContext,
    ) -> str:
        context_text = format_context_for_llm(context)

        system_prompt = self._get_enhanced_system_prompt(plan.primary_intent)
        user_prompt = self._build_enhanced_user_prompt(question, plan, context_text)

        from openai import AsyncOpenAI
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.llm_temperature,
            max_tokens=2000,
        )

        return response.choices[0].message.content.strip()

    def _get_enhanced_system_prompt(self, intent: QueryIntent) -> str:
        base_prompt = """You are an expert code analyst. Synthesize code analysis results
to provide accurate, actionable answers to developer questions.

## Context Available to You
You have access to rich context extracted from the codebase:
- **Code snippets**: Implementation code with file paths and line numbers
- **Call graphs**: Which functions call which (callers and callees)
- **Inheritance hierarchies**: Class relationships and method overrides
- **Summaries**: AI-generated descriptions of code purpose and behavior
- **File context**: What else exists in relevant files

## Response Requirements

**TRACEABILITY** (Critical)
- Every claim must cite its source: `file_path:line_number` or `ClassName.method`
- Distinguish between what you see in code vs. what's in summaries
- If you infer something, explicitly state it as an inference

**ACCURACY**
- Only state facts supported by the provided context
- Use precise language: "calls" vs "may call", "contains" vs "appears to"
- Acknowledge gaps: "The context doesn't show X, but based on Y..."

**STRUCTURE**
- Lead with the direct answer
- Support with evidence from the context
- Use headers and bullet points for complex explanations
- Include focused code snippets when they clarify your points

**COMPLETENESS**
- Address all parts of the question
- Note related information that might be useful
- Suggest what to look at next if the answer is partial"""

        intent_additions = {
            QueryIntent.FIND_CALLERS: """

## Intent: Finding Callers
Focus your answer on:
- WHERE the entity is called from (list all call sites with file:line)
- HOW it's being used in each context (what parameters, what happens with the result)
- WHY it might be called in each case (infer from context)
- FREQUENCY/IMPORTANCE: Which callers are most significant?""",

            QueryIntent.FIND_CALLEES: """

## Intent: Finding Dependencies
Focus your answer on:
- WHAT the entity calls or depends on (list with file:line references)
- WHY each dependency exists (what purpose does each call serve?)
- CRITICAL DEPENDENCIES: Which callees are essential vs optional?
- EXTERNAL vs INTERNAL: Note any calls to external libraries/APIs""",

            QueryIntent.FIND_CALL_CHAIN: """

## Intent: Tracing Call Chain
Focus your answer on:
- The COMPLETE PATH from source to target
- Each HOP in the chain with file:line references
- TRANSFORMATIONS: How does data change at each step?
- BRANCHES: Are there multiple possible paths?""",

            QueryIntent.FIND_HIERARCHY: """

## Intent: Class Hierarchy Analysis
Focus your answer on:
- The FULL inheritance tree (both ancestors and descendants)
- What each level ADDS or OVERRIDES
- DESIGN PATTERN: Is this a known pattern (Template Method, Strategy, etc.)?
- USAGE: How should developers work with this hierarchy?""",

            QueryIntent.EXPLAIN_IMPLEMENTATION: """

## Intent: Implementation Deep-Dive
Provide a thorough explanation of HOW the code works:
- ALGORITHM/LOGIC: Step-by-step walkthrough of the implementation
- KEY DECISIONS: Why is it implemented this way?
- EDGE CASES: How does it handle unusual inputs or errors?
- DEPENDENCIES: What does it rely on to work correctly?""",

            QueryIntent.EXPLAIN_DATA_FLOW: """

## Intent: Data Flow Analysis
Trace how data moves through the system:
- ENTRY POINT: Where does the data originate?
- TRANSFORMATIONS: What happens to the data at each step?
- HANDLERS: What components touch the data?
- EXIT POINTS: Where does the data end up?""",

            QueryIntent.SEARCH_FUNCTIONALITY: """

## Intent: Finding Functionality
Help the developer understand what code handles this functionality:
- LOCATIONS: Where is this functionality implemented?
- COMPONENTS: What classes/functions are involved?
- USAGE: How would a developer use or extend this?
- RELATED: What other functionality is nearby?""",
        }

        return base_prompt + intent_additions.get(intent, "")

    def _build_enhanced_user_prompt(
        self,
        question: str,
        plan: QueryPlan,
        context_text: str,
    ) -> str:
        prompt_parts = [
            "# Developer Question\n",
            f"**{question}**\n",
        ]

        prompt_parts.append("\n## Query Analysis\n")
        prompt_parts.append(f"- **Detected Intent**: {plan.primary_intent.value}\n")

        if plan.entities:
            entities_str = ", ".join(f"`{e.name}`" for e in plan.entities)
            prompt_parts.append(f"- **Key Entities**: {entities_str}\n")

        if plan.requires_multi_hop:
            prompt_parts.append(
                f"- **Reasoning Depth**: Multi-hop analysis (up to {plan.max_hops} hops)\n"
            )

        if plan.reasoning:
            prompt_parts.append(f"- **Search Strategy**: {plan.reasoning}\n")

        prompt_parts.append(f"\n{context_text}\n")

        prompt_parts.append("\n---\n")
        prompt_parts.append("## Your Task\n")
        prompt_parts.append(
            "Using the context above, provide a complete answer to the question.\n\n"
        )
        prompt_parts.append("**Requirements:**\n")
        prompt_parts.append("1. Start with a direct, concise answer\n")
        prompt_parts.append("2. Support every claim with references (file:line or entity names)\n")
        prompt_parts.append("3. Include relevant code snippets when they help clarify\n")
        prompt_parts.append("4. If context is incomplete, state what's known and what's missing\n")
        prompt_parts.append("5. Suggest next steps if more information might be needed\n")

        return "".join(prompt_parts)

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
