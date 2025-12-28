import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from lattice.shared.config import get_settings
from lattice.shared.exceptions import QueryError
from lattice.infrastructure.qdrant import CollectionName, QdrantManager
from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.prompts import get_prompt
from lattice.querying.context import ContextBuilder, EnrichedContext, format_context_for_llm
from lattice.querying.graph_reasoning import GraphContext, GraphReasoningEngine
from lattice.querying.query_planner import QueryIntent, QueryPlan, QueryPlanner
from lattice.querying.ranking import HybridRanker, RankedResult
from lattice.querying.responder import ResponseGenerator
from lattice.querying.vector_search import VectorSearcher

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
    def __init__(
        self,
        memgraph: MemgraphClient,
        qdrant: QdrantManager,
        planner: QueryPlanner,
        graph_engine: GraphReasoningEngine,
        vector_searcher: VectorSearcher,
        context_builder: ContextBuilder,
        ranker: HybridRanker,
        responder: ResponseGenerator,
    ):
        self._memgraph = memgraph
        self._qdrant = qdrant
        self._planner = planner
        self._graph_engine = graph_engine
        self._vector_searcher = vector_searcher
        self._context_builder = context_builder
        self._ranker = ranker
        self._responder = responder

    async def close(self) -> None:
        logger.info("Closing query engine")
        await self._memgraph.close()
        await self._qdrant.close()

    async def query(
        self,
        question: str,
        limit: int | None = None,
        language: str | None = None,
        use_llm_planning: bool = True,
        project_name: str | None = None,
    ) -> QueryResult:
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
        base_prompt = get_prompt("query", "enhanced_system")

        intent_prompt_map = {
            QueryIntent.FIND_CALLERS: "intent_find_callers",
            QueryIntent.FIND_CALLEES: "intent_find_callees",
            QueryIntent.FIND_CALL_CHAIN: "intent_find_call_chain",
            QueryIntent.FIND_HIERARCHY: "intent_find_hierarchy",
            QueryIntent.EXPLAIN_IMPLEMENTATION: "intent_explain_implementation",
            QueryIntent.EXPLAIN_DATA_FLOW: "intent_explain_data_flow",
            QueryIntent.SEARCH_FUNCTIONALITY: "intent_search_functionality",
        }

        prompt_name = intent_prompt_map.get(intent)
        if prompt_name:
            return base_prompt + get_prompt("query", prompt_name)
        return base_prompt

    def _build_enhanced_user_prompt(
        self,
        question: str,
        plan: QueryPlan,
        context_text: str,
    ) -> str:
        entities_section = ""
        if plan.entities:
            entities_str = ", ".join(f"`{e.name}`" for e in plan.entities)
            entities_section = f"- **Key Entities**: {entities_str}"

        multi_hop_section = ""
        if plan.requires_multi_hop:
            multi_hop_section = (
                f"- **Reasoning Depth**: Multi-hop analysis (up to {plan.max_hops} hops)"
            )

        reasoning_section = ""
        if plan.reasoning:
            reasoning_section = f"- **Search Strategy**: {plan.reasoning}"

        return get_prompt(
            "query",
            "enhanced_user",
            question=question,
            intent=plan.primary_intent.value,
            entities_section=entities_section,
            multi_hop_section=multi_hop_section,
            reasoning_section=reasoning_section,
            context_text=context_text,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
