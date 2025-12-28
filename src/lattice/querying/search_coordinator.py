import asyncio
import logging
from typing import Any

from lattice.querying.graph_reasoning import GraphContext, GraphReasoningEngine
from lattice.querying.query_planner import QueryIntent, QueryPlan
from lattice.querying.vector_search import VectorSearcher
from lattice.shared.config import get_settings

logger = logging.getLogger(__name__)


class SearchCoordinator:
    def __init__(
        self,
        vector_searcher: VectorSearcher,
        graph_engine: GraphReasoningEngine,
    ):
        self._vector_searcher = vector_searcher
        self._graph_engine = graph_engine

    async def execute_vector_search(
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

    async def get_centrality_scores(
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
        entities = list(entities)[: settings.query.max_centrality_lookups]

        scores: dict[str, dict[str, int]] = {}
        if entities:
            tasks = [self._graph_engine.get_entity_centrality(name) for name in entities]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(entities, results):
                if isinstance(result, dict):
                    scores[name] = result

        return scores
