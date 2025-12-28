import logging
from typing import Any

from lattice.shared.exceptions import QueryError
from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.querying.graph_reasoning.context_builder import (
    gather_caller_context,
    gather_callee_context,
    gather_call_chain_context,
    gather_comprehensive_context,
    gather_dependency_context,
    gather_hierarchy_context,
    gather_implementation_context,
)
from lattice.querying.graph_reasoning.entity_finder import find_entity, find_entity_fuzzy
from lattice.querying.graph_reasoning.graph_queries import (
    find_class_with_methods,
    find_file_context,
    get_entity_centrality,
)
from lattice.querying.graph_reasoning.models import (
    MAX_RESULTS_PER_QUERY,
    GraphContext,
    GraphNode,
    GraphPath,
)
from lattice.querying.graph_reasoning.node_utils import dict_to_node, result_to_node
from lattice.querying.graph_reasoning.traversal import (
    find_call_chain,
    find_full_hierarchy,
    find_implementation_context,
    find_transitive_callers,
    find_transitive_callees,
)
from lattice.querying.query_planner import QueryIntent, QueryPlan

logger = logging.getLogger(__name__)


class GraphReasoningEngine:
    def __init__(self, client: MemgraphClient):
        self.client = client

    async def execute_query_plan(self, plan: QueryPlan) -> GraphContext:
        logger.debug(f"Executing query plan: intent={plan.primary_intent}")

        context = GraphContext(
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

        try:
            for entity in plan.entities:
                if entity.is_primary or not context.primary_entities:
                    nodes = await find_entity(self.client, entity.name, entity.entity_type)
                    context.primary_entities.extend(nodes)

            if not context.primary_entities:
                for entity in plan.entities:
                    nodes = await find_entity_fuzzy(self.client, entity.name)
                    context.primary_entities.extend(nodes)

            if plan.primary_intent in (QueryIntent.FIND_CALLERS, QueryIntent.FIND_USAGES):
                await gather_caller_context(self.client, context, plan)

            elif plan.primary_intent == QueryIntent.FIND_CALLEES:
                await gather_callee_context(self.client, context, plan)

            elif plan.primary_intent == QueryIntent.FIND_CALL_CHAIN:
                await gather_call_chain_context(self.client, context, plan)

            elif plan.primary_intent in (QueryIntent.FIND_HIERARCHY, QueryIntent.FIND_IMPLEMENTATIONS):
                await gather_hierarchy_context(self.client, context, plan)

            elif plan.primary_intent == QueryIntent.EXPLAIN_IMPLEMENTATION:
                await gather_implementation_context(self.client, context, plan)

            elif plan.primary_intent in (QueryIntent.FIND_DEPENDENCIES, QueryIntent.FIND_DEPENDENTS):
                await gather_dependency_context(self.client, context, plan)

            else:
                await gather_comprehensive_context(self.client, context, plan)

            logger.debug(
                f"Context gathered: {len(context.primary_entities)} primary, "
                f"{len(context.callers)} callers, {len(context.callees)} callees"
            )

            return context

        except Exception as e:
            logger.error(f"Error executing query plan: {e}")
            raise QueryError(f"Graph reasoning failed: {e}", cause=e)

    async def find_transitive_callers(
        self,
        entity_name: str,
        max_hops: int = 3,
        limit: int = MAX_RESULTS_PER_QUERY,
    ) -> list[GraphNode]:
        return await find_transitive_callers(self.client, entity_name, max_hops, limit)

    async def find_transitive_callees(
        self,
        entity_name: str,
        max_hops: int = 3,
        limit: int = MAX_RESULTS_PER_QUERY,
    ) -> list[GraphNode]:
        return await find_transitive_callees(self.client, entity_name, max_hops, limit)

    async def find_call_chain(
        self,
        source_name: str,
        target_name: str,
        max_hops: int = 5,
    ) -> list[GraphPath]:
        return await find_call_chain(self.client, source_name, target_name, max_hops)

    async def find_full_hierarchy(
        self,
        class_name: str,
    ) -> tuple[GraphNode | None, list[GraphNode], list[GraphNode]]:
        return await find_full_hierarchy(self.client, class_name)

    async def find_implementation_context(self, entity_name: str) -> dict[str, Any]:
        return await find_implementation_context(self.client, entity_name)

    async def find_class_with_methods(
        self,
        class_name: str,
    ) -> tuple[GraphNode | None, list[GraphNode]]:
        return await find_class_with_methods(self.client, class_name)

    async def find_file_context(self, file_path: str) -> list[dict[str, Any]]:
        return await find_file_context(self.client, file_path)

    async def get_entity_centrality(self, entity_name: str) -> dict[str, int]:
        return await get_entity_centrality(self.client, entity_name)

    def _result_to_node(self, result: dict[str, Any]) -> GraphNode:
        return result_to_node(result)

    def _dict_to_node(self, d: dict[str, Any]) -> GraphNode:
        return dict_to_node(d)
