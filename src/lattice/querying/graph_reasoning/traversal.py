import logging
from typing import Any

from lattice.infrastructure.memgraph import MemgraphClient
from lattice.querying.graph_reasoning.models import (
    MAX_PATH_LENGTH,
    MAX_RESULTS_PER_QUERY,
    MAX_TRAVERSAL_DEPTH,
    GraphNode,
    GraphPath,
)
from lattice.querying.graph_reasoning.node_utils import dict_to_node, result_to_node
from lattice.querying.graph_reasoning.queries import MultiHopGraphQueries
from lattice.shared.config import QueryConfig
from lattice.shared.exceptions import GraphError

logger = logging.getLogger(__name__)


async def find_transitive_callers(
    client: MemgraphClient,
    entity_name: str,
    max_hops: int = QueryConfig.fallback_max_hops,
    limit: int = MAX_RESULTS_PER_QUERY,
) -> list[GraphNode]:
    max_hops = min(max_hops, MAX_TRAVERSAL_DEPTH)
    query = MultiHopGraphQueries.FIND_TRANSITIVE_CALLERS.format(max_hops=max_hops)

    try:
        results = await client.execute(
            query,
            {"name": entity_name, "limit": limit},
        )
        return [result_to_node(r) for r in results]
    except GraphError as e:
        logger.warning(f"Error finding transitive callers: {e}")
        return []


async def find_transitive_callees(
    client: MemgraphClient,
    entity_name: str,
    max_hops: int = QueryConfig.fallback_max_hops,
    limit: int = MAX_RESULTS_PER_QUERY,
) -> list[GraphNode]:
    max_hops = min(max_hops, MAX_TRAVERSAL_DEPTH)
    query = MultiHopGraphQueries.FIND_TRANSITIVE_CALLEES.format(max_hops=max_hops)

    try:
        results = await client.execute(
            query,
            {"name": entity_name, "limit": limit},
        )
        return [result_to_node(r) for r in results]
    except GraphError as e:
        logger.warning(f"Error finding transitive callees: {e}")
        return []


async def find_call_chain(
    client: MemgraphClient,
    source_name: str,
    target_name: str,
    max_hops: int = MAX_PATH_LENGTH,
) -> list[GraphPath]:
    max_hops = min(max_hops, MAX_PATH_LENGTH)
    query = MultiHopGraphQueries.FIND_ALL_PATHS.format(max_hops=max_hops)

    try:
        results = await client.execute(
            query,
            {"source_name": source_name, "target_name": target_name},
        )

        paths = []
        for r in results:
            path_nodes = r.get("path_nodes", [])
            if path_nodes:
                nodes = [dict_to_node(n) for n in path_nodes]
                paths.append(
                    GraphPath(
                        nodes=nodes,
                        relationships=["CALLS"] * (len(nodes) - 1),
                        total_length=r.get("path_length", len(nodes) - 1),
                        path_type="call_chain",
                    )
                )

        return paths
    except GraphError as e:
        logger.warning(f"Error finding call chain: {e}")
        return []


async def find_full_hierarchy(
    client: MemgraphClient,
    class_name: str,
) -> tuple[GraphNode | None, list[GraphNode], list[GraphNode]]:
    try:
        results = await client.execute(
            MultiHopGraphQueries.FIND_FULL_HIERARCHY,
            {"name": class_name},
        )

        if not results:
            return None, [], []

        r = results[0]
        target_node = dict_to_node(r.get("target_node", {}))

        ancestors = []
        descendants = []

        for h in r.get("hierarchy_nodes", []):
            node = dict_to_node(h)
            if h.get("direction") == "ancestor":
                ancestors.append(node)
            else:
                descendants.append(node)

        return target_node, ancestors, descendants
    except GraphError as e:
        logger.warning(f"Error finding hierarchy: {e}")
        return None, [], []


async def find_implementation_context(
    client: MemgraphClient,
    entity_name: str,
) -> dict[str, Any]:
    try:
        results = await client.execute(
            MultiHopGraphQueries.FIND_IMPLEMENTATION_CONTEXT,
            {"name": entity_name},
        )

        if not results:
            return {}

        r = results[0]
        return {
            "entity": dict_to_node(r.get("entity_node", {})),
            "callers": [dict_to_node(c) for c in r.get("callers", []) if c.get("name")],
            "callees": [dict_to_node(c) for c in r.get("callees", []) if c.get("name")],
            "siblings": [dict_to_node(s) for s in r.get("siblings", []) if s.get("name")],
        }
    except GraphError as e:
        logger.warning(f"Error finding implementation context: {e}")
        return {}
