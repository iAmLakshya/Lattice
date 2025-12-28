import logging
from typing import Any

from lattice.infrastructure.memgraph import MemgraphClient
from lattice.querying.graph_reasoning.models import GraphNode
from lattice.querying.graph_reasoning.node_utils import dict_to_node
from lattice.querying.graph_reasoning.queries import MultiHopGraphQueries
from lattice.shared.exceptions import GraphError

logger = logging.getLogger(__name__)


async def find_class_with_methods(
    client: MemgraphClient,
    class_name: str,
) -> tuple[GraphNode | None, list[GraphNode]]:
    try:
        results = await client.execute(
            MultiHopGraphQueries.FIND_CLASS_WITH_METHODS,
            {"name": class_name},
        )

        if not results:
            return None, []

        r = results[0]
        class_node = dict_to_node(r.get("class_node", {}))
        methods = [dict_to_node(m) for m in r.get("methods", []) if m.get("name")]

        return class_node, methods
    except GraphError as e:
        logger.warning(f"Error finding class with methods: {e}")
        return None, []


async def find_file_context(
    client: MemgraphClient,
    file_path: str,
) -> list[dict[str, Any]]:
    try:
        results = await client.execute(
            MultiHopGraphQueries.FIND_FILE_CONTEXT,
            {"file_path": file_path},
        )

        entities = []
        for r in results:
            entity = dict_to_node(r.get("entity_node", {}))
            entities.append(
                {
                    "entity": entity,
                    "callee_count": r.get("callee_count", 0),
                    "caller_count": r.get("caller_count", 0),
                    "parent_class": r.get("parent_class"),
                    "child_count": r.get("child_count", 0),
                }
            )

        return entities
    except GraphError as e:
        logger.warning(f"Error finding file context: {e}")
        return []


async def get_entity_centrality(
    client: MemgraphClient,
    entity_name: str,
) -> dict[str, int]:
    try:
        results = await client.execute(
            MultiHopGraphQueries.GET_ENTITY_CENTRALITY,
            {"name": entity_name},
        )

        if not results:
            return {"in_degree": 0, "out_degree": 0, "total_degree": 0}

        r = results[0]
        return {
            "in_degree": r.get("in_degree", 0),
            "out_degree": r.get("out_degree", 0),
            "total_degree": r.get("total_degree", 0),
            "relationship_count": r.get("relationship_count", 0),
        }
    except GraphError as e:
        logger.warning(f"Error getting entity centrality: {e}")
        return {"in_degree": 0, "out_degree": 0, "total_degree": 0}
