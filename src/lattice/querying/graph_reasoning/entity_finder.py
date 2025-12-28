from lattice.infrastructure.memgraph import MemgraphClient
from lattice.querying.graph_reasoning.models import GraphNode
from lattice.querying.graph_reasoning.node_utils import result_to_node
from lattice.querying.graph_reasoning.queries import MultiHopGraphQueries
from lattice.shared.exceptions import GraphError


async def find_entity(
    client: MemgraphClient,
    name: str,
    entity_type: str | None = None,
) -> list[GraphNode]:
    if entity_type:
        type_label = entity_type.capitalize()
        query = f"""
        MATCH (n:{type_label})
        WHERE n.name = $name OR n.qualified_name = $name
        RETURN
            labels(n)[0] as node_type,
            n.name as name,
            n.qualified_name as qualified_name,
            n.file_path as file_path,
            n.signature as signature,
            n.docstring as docstring,
            n.summary as summary,
            n.start_line as start_line,
            n.end_line as end_line,
            n.is_async as is_async,
            n.parent_class as parent_class
        """
    else:
        query = """
        MATCH (n)
        WHERE n.name = $name OR n.qualified_name = $name
        RETURN
            labels(n)[0] as node_type,
            n.name as name,
            n.qualified_name as qualified_name,
            n.file_path as file_path,
            n.signature as signature,
            n.docstring as docstring,
            n.summary as summary,
            n.start_line as start_line,
            n.end_line as end_line,
            n.is_async as is_async,
            n.parent_class as parent_class
        """

    try:
        results = await client.execute(query, {"name": name})
        return [result_to_node(r) for r in results]
    except GraphError:
        return []


async def find_entity_fuzzy(
    client: MemgraphClient,
    name: str,
    limit: int = 10,
) -> list[GraphNode]:
    try:
        results = await client.execute(
            MultiHopGraphQueries.FIND_ENTITY_FUZZY,
            {"name": name, "limit": limit},
        )
        return [result_to_node(r) for r in results]
    except GraphError:
        return []
