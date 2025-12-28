import logging
from typing import Any

from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import CollectionName, QdrantManager
from lattice.shared.exceptions import QueryError

logger = logging.getLogger(__name__)


async def get_codebase_statistics(
    memgraph: MemgraphClient,
    qdrant: QdrantManager,
) -> dict[str, Any]:
    try:
        graph_stats = await memgraph.execute(
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
            code_info = await qdrant.get_collection_info(CollectionName.CODE_CHUNKS.value)
            vector_count = code_info.points_count
        except Exception:
            vector_count = 0

        stats = graph_stats[0] if graph_stats else {}
        stats["vector_count"] = vector_count

        return stats

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise QueryError("Failed to get statistics", cause=e)
