import asyncio
import logging
import time
from typing import Any

from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager
from lattice.querying.context import ContextBuilder
from lattice.querying.graph_reasoning import GraphContext, GraphReasoningEngine
from lattice.querying.models import QueryResult
from lattice.querying.query_planner import QueryPlan, QueryPlanner
from lattice.querying.ranking import HybridRanker, RankedResult
from lattice.querying.response_builder import ResponseBuilder
from lattice.querying.search_coordinator import SearchCoordinator
from lattice.querying.statistics import get_codebase_statistics
from lattice.shared.config import get_settings
from lattice.shared.exceptions import QueryError

logger = logging.getLogger(__name__)


class QueryEngine:
    def __init__(
        self,
        memgraph: MemgraphClient,
        qdrant: QdrantManager,
        planner: QueryPlanner,
        graph_engine: GraphReasoningEngine,
        context_builder: ContextBuilder,
        ranker: HybridRanker,
        response_builder: ResponseBuilder,
        search_coordinator: SearchCoordinator,
    ):
        self._memgraph = memgraph
        self._qdrant = qdrant
        self._planner = planner
        self._graph_engine = graph_engine
        self._context_builder = context_builder
        self._ranker = ranker
        self._response_builder = response_builder
        self._search_coordinator = search_coordinator

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

        try:
            logger.info(f"Executing query: {question}")
            plan, stats = await self._plan_query(question, use_llm_planning)
            graph_context, vector_results, graph_time = await self._execute_searches(
                question, plan, limit, language, project_name
            )
            stats["graph_time_ms"] = graph_time
            ranked_results, stats = await self._rank_and_enrich(
                plan, graph_context, vector_results, stats
            )
            start = time.time()
            answer = await self._response_builder.generate_response(
                question, plan, ranked_results[:limit], stats.get("enriched_context")
            )
            stats["response_time_ms"] = int((time.time() - start) * 1000)
            logger.info(f"Query completed: {len(ranked_results)} results")
            return QueryResult(
                answer=answer,
                sources=ranked_results[:limit],
                query_plan=plan,
                context=stats.pop("enriched_context"),
                graph_context=graph_context,
                execution_stats=stats,
            )
        except QueryError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during query: {e}")
            raise QueryError("Query execution failed", cause=e)

    async def _plan_query(
        self, question: str, use_llm_planning: bool
    ) -> tuple[QueryPlan, dict[str, Any]]:
        start = time.time()
        plan = (
            await self._planner.plan_query(question)
            if use_llm_planning
            else self._planner._fallback_plan(question)
        )
        return plan, {"planning_time_ms": int((time.time() - start) * 1000)}

    async def _execute_searches(
        self,
        question: str,
        plan: QueryPlan,
        limit: int,
        language: str | None,
        project_name: str | None,
    ) -> tuple[GraphContext, list[dict[str, Any]], int]:
        start = time.time()
        graph_task = self._graph_engine.execute_query_plan(plan)
        vector_task = self._search_coordinator.execute_vector_search(
            question, plan, limit, language, project_name
        )
        graph_context, vector_results = await asyncio.gather(
            graph_task, vector_task, return_exceptions=True
        )
        graph_time = int((time.time() - start) * 1000)
        if isinstance(graph_context, Exception):
            logger.warning(f"Graph search failed: {graph_context}")
            graph_context = GraphContext.empty()
        if isinstance(vector_results, Exception):
            logger.warning(f"Vector search failed: {vector_results}")
            vector_results = []
        return graph_context, vector_results, graph_time

    async def _rank_and_enrich(
        self,
        plan: QueryPlan,
        graph_context: GraphContext,
        vector_results: list[dict[str, Any]],
        stats: dict[str, Any],
    ) -> tuple[list[RankedResult], dict[str, Any]]:
        start = time.time()
        centrality_scores = await self._search_coordinator.get_centrality_scores(
            graph_context, vector_results
        )
        stats["vector_time_ms"] = int((time.time() - start) * 1000)
        start = time.time()
        ranked_results = self._ranker.rank_results(
            plan, graph_context, vector_results, centrality_scores
        )
        stats["ranking_time_ms"] = int((time.time() - start) * 1000)
        start = time.time()
        enriched_context = await self._context_builder.build_enriched_context(
            plan, graph_context, vector_results
        )
        stats["context_time_ms"] = int((time.time() - start) * 1000)
        stats["enriched_context"] = enriched_context
        return ranked_results, stats

    async def search(
        self,
        query: str,
        limit: int | None = None,
        language: str | None = None,
        project_name: str | None = None,
    ) -> list[RankedResult]:
        settings = get_settings()
        limit = limit or settings.query.search_limit
        try:
            logger.info(f"Executing search: {query}")
            plan = await self._planner.plan_query(query)
            graph_context, vector_results = await asyncio.gather(
                self._graph_engine.execute_query_plan(plan),
                self._search_coordinator.execute_vector_search(
                    query, plan, limit * 2, language, project_name
                ),
            )
            centrality_scores = await self._search_coordinator.get_centrality_scores(
                graph_context, vector_results
            )
            ranked_results = self._ranker.rank_results(
                plan, graph_context, vector_results, centrality_scores
            )
            logger.info(f"Search completed: {len(ranked_results[:limit])} results")
            return ranked_results[:limit]
        except QueryError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise QueryError("Search execution failed", cause=e)

    async def explain_entity(self, entity_name: str) -> QueryResult:
        return await self.query(f"Explain how {entity_name} works and is used in the codebase")

    async def find_call_path(self, source_name: str, target_name: str) -> QueryResult:
        return await self.query(
            f"How does {source_name} eventually call {target_name}? Show the call chain."
        )

    async def get_statistics(self) -> dict[str, Any]:
        return await get_codebase_statistics(self._memgraph, self._qdrant)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
