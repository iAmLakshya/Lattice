"""Graph-based search using Memgraph."""

import logging
from dataclasses import dataclass

from lattice.infrastructure.memgraph import GraphStatistics, MemgraphClient, SearchQueries
from lattice.shared.config import QueryConfig
from lattice.shared.exceptions import GraphError, QueryError
from lattice.shared.types import EntityType

logger = logging.getLogger(__name__)


@dataclass
class EntitySearchResult:
    name: str
    qualified_name: str
    entity_type: str
    file_path: str
    summary: str | None = None
    signature: str | None = None
    start_line: int | None = None
    end_line: int | None = None


@dataclass
class RelatedEntityResult:
    name: str
    qualified_name: str
    entity_type: str
    file_path: str
    summary: str | None
    distance: int


def _validate_entity_type(entity_type: str) -> None:
    valid_types = {e.value for e in EntityType} | {"Class", "Function", "Method"}
    if entity_type not in valid_types:
        raise QueryError(f"Invalid entity type: {entity_type}")


def _build_entity_query(entity_type: str | None) -> str:
    if entity_type:
        return f"""
        MATCH (n:{entity_type})
        WHERE n.name = $name OR n.qualified_name = $name
        RETURN n.name as name,
               n.qualified_name as qualified_name,
               n.file_path as file_path,
               n.summary as summary,
               n.signature as signature,
               n.start_line as start_line,
               n.end_line as end_line
        """
    else:
        return """
        MATCH (n)
        WHERE n.name = $name OR n.qualified_name = $name
        RETURN n.name as name,
               n.qualified_name as qualified_name,
               labels(n)[0] as type,
               n.file_path as file_path,
               n.summary as summary,
               n.signature as signature,
               n.start_line as start_line,
               n.end_line as end_line
        """


async def find_entity_by_name(
    client: MemgraphClient,
    name: str,
    entity_type: str | None = None,
) -> list[dict]:
    if not name or not name.strip():
        raise QueryError("Entity name cannot be empty")

    if entity_type:
        _validate_entity_type(entity_type)

    try:
        logger.debug(f"Searching for entity: {name}, type: {entity_type}")
        query = _build_entity_query(entity_type)
        results = await client.execute(query, {"name": name})
        logger.debug(f"Found {len(results)} entities")
        return results

    except GraphError as e:
        logger.error(f"Graph error finding entity: {e}")
        raise QueryError(f"Failed to find entity: {name}", cause=e)


async def find_callers(client: MemgraphClient, function_name: str) -> list[dict]:
    if not function_name or not function_name.strip():
        raise QueryError("Function name cannot be empty")

    try:
        logger.debug(f"Finding callers of: {function_name}")
        results = await client.execute(
            SearchQueries.FIND_CALLERS,
            {"qualified_name": function_name},
        )
        logger.debug(f"Found {len(results)} callers")
        return results

    except GraphError as e:
        logger.error(f"Graph error finding callers: {e}")
        raise QueryError(f"Failed to find callers for: {function_name}", cause=e)


async def find_callees(client: MemgraphClient, function_name: str) -> list[dict]:
    if not function_name or not function_name.strip():
        raise QueryError("Function name cannot be empty")

    try:
        logger.debug(f"Finding callees of: {function_name}")
        results = await client.execute(
            SearchQueries.FIND_CALLEES,
            {"qualified_name": function_name},
        )
        logger.debug(f"Found {len(results)} callees")
        return results

    except GraphError as e:
        logger.error(f"Graph error finding callees: {e}")
        raise QueryError(f"Failed to find callees for: {function_name}", cause=e)


async def find_class_hierarchy(client: MemgraphClient, class_name: str) -> list[dict]:
    if not class_name or not class_name.strip():
        raise QueryError("Class name cannot be empty")

    try:
        logger.debug(f"Finding class hierarchy for: {class_name}")
        results = await client.execute(
            SearchQueries.FIND_CLASS_HIERARCHY,
            {"qualified_name": class_name},
        )
        logger.debug(f"Found {len(results)} hierarchy results")
        return results

    except GraphError as e:
        logger.error(f"Graph error finding class hierarchy: {e}")
        raise QueryError(f"Failed to find hierarchy for: {class_name}", cause=e)


async def find_file_dependencies(client: MemgraphClient, file_path: str) -> list[dict]:
    if not file_path or not file_path.strip():
        raise QueryError("File path cannot be empty")

    try:
        logger.debug(f"Finding dependencies for file: {file_path}")
        results = await client.execute(
            SearchQueries.FIND_FILE_DEPENDENCIES,
            {"path": file_path},
        )
        logger.debug(f"Found {len(results)} dependencies")
        return results

    except GraphError as e:
        logger.error(f"Graph error finding file dependencies: {e}")
        raise QueryError(f"Failed to find dependencies for: {file_path}", cause=e)


async def get_file_entities(client: MemgraphClient, file_path: str) -> list[dict]:
    if not file_path or not file_path.strip():
        raise QueryError("File path cannot be empty")

    try:
        logger.debug(f"Getting entities for file: {file_path}")
        results = await client.execute(
            SearchQueries.GET_FILE_ENTITIES,
            {"path": file_path},
        )
        logger.debug(f"Found {len(results)} entities")
        return results

    except GraphError as e:
        logger.error(f"Graph error getting file entities: {e}")
        raise QueryError(f"Failed to get entities for: {file_path}", cause=e)


async def search_by_name(
    client: MemgraphClient,
    query: str,
    limit: int | None = None,
) -> list[dict]:
    if limit is None:
        limit = QueryConfig.default_search_limit

    if not query or not query.strip():
        raise QueryError("Search query cannot be empty")

    try:
        logger.debug(f"Searching by name: {query}, limit: {limit}")
        results = await client.execute(
            SearchQueries.SEARCH_BY_NAME,
            {"query": query, "limit": limit},
        )
        logger.debug(f"Found {len(results)} matches")
        return results

    except GraphError as e:
        logger.error(f"Graph error searching by name: {e}")
        raise QueryError(f"Failed to search for: {query}", cause=e)


async def find_related_entities(
    client: MemgraphClient,
    entity_name: str,
    max_depth: int | None = None,
) -> list[dict]:
    if max_depth is None:
        max_depth = QueryConfig.default_max_depth

    if not entity_name or not entity_name.strip():
        raise QueryError("Entity name cannot be empty")

    if max_depth < 1:
        raise QueryError("Max depth must be at least 1")

    try:
        related_entities_limit = QueryConfig.related_entities_limit
        logger.debug(f"Finding related entities for: {entity_name}, depth: {max_depth}")
        query = f"""
        MATCH (source)
        WHERE source.name = $name OR source.qualified_name = $name
        MATCH path = (source)-[*1..{max_depth}]-(related)
        WHERE source <> related
        RETURN DISTINCT related.name as name,
               related.qualified_name as qualified_name,
               labels(related)[0] as type,
               related.file_path as file_path,
               related.summary as summary,
               length(path) as distance
        ORDER BY distance
        LIMIT {related_entities_limit}
        """
        results = await client.execute(query, {"name": entity_name})
        logger.debug(f"Found {len(results)} related entities")
        return results

    except GraphError as e:
        logger.error(f"Graph error finding related entities: {e}")
        raise QueryError(f"Failed to find related entities for: {entity_name}", cause=e)


async def get_statistics(client: MemgraphClient) -> dict:
    try:
        logger.debug("Getting graph statistics")
        stats = GraphStatistics(client)
        return await stats.get_entity_counts()

    except GraphError as e:
        logger.error(f"Graph error getting statistics: {e}")
        raise QueryError("Failed to get graph statistics", cause=e)
