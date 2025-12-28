"""Vector-based semantic search using Qdrant."""

import logging
from dataclasses import dataclass

from lattice.infrastructure.llm import BaseEmbeddingProvider
from lattice.infrastructure.qdrant import CollectionName, QdrantManager
from lattice.shared.config import QueryConfig
from lattice.shared.exceptions import EmbeddingError, QueryError, VectorStoreError

logger = logging.getLogger(__name__)


@dataclass
class CodeSearchResult:
    score: float
    file_path: str
    entity_type: str
    entity_name: str
    content: str
    language: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    graph_node_id: str | None = None


@dataclass
class SummarySearchResult:
    score: float
    file_path: str
    entity_type: str
    entity_name: str
    summary: str
    graph_node_id: str | None = None


def _transform_code_result(result: dict) -> dict:
    payload = result["payload"]
    return {
        "score": result["score"],
        "file_path": payload.get("file_path"),
        "entity_type": payload.get("entity_type"),
        "entity_name": payload.get("entity_name"),
        "language": payload.get("language"),
        "content": payload.get("content"),
        "start_line": payload.get("start_line"),
        "end_line": payload.get("end_line"),
        "graph_node_id": payload.get("graph_node_id"),
    }


def _transform_summary_result(result: dict) -> dict:
    payload = result["payload"]
    return {
        "score": result["score"],
        "file_path": payload.get("file_path"),
        "entity_type": payload.get("entity_type"),
        "entity_name": payload.get("entity_name"),
        "summary": payload.get("summary"),
        "graph_node_id": payload.get("graph_node_id"),
    }


def _transform_similar_code_result(result: dict) -> dict:
    payload = result["payload"]
    return {
        "score": result["score"],
        "file_path": payload.get("file_path"),
        "entity_type": payload.get("entity_type"),
        "entity_name": payload.get("entity_name"),
        "content": payload.get("content"),
        "start_line": payload.get("start_line"),
        "end_line": payload.get("end_line"),
    }


async def search_code(
    qdrant: QdrantManager,
    embedder: BaseEmbeddingProvider,
    query: str,
    limit: int | None = None,
    language: str | None = None,
    entity_type: str | None = None,
    project_name: str | None = None,
) -> list[dict]:
    if limit is None:
        limit = QueryConfig.default_search_limit

    if not query or not query.strip():
        raise QueryError("Search query cannot be empty")

    try:
        logger.debug(f"Searching code: query='{query}', limit={limit}, language={language}")
        query_embedding = await embedder.embed(query)

        filters = {}
        if language:
            filters["language"] = language
        if entity_type:
            filters["entity_type"] = entity_type
        if project_name:
            filters["project_name"] = project_name

        results = await qdrant.search(
            collection=CollectionName.CODE_CHUNKS.value,
            query_vector=query_embedding,
            limit=limit,
            filters=filters if filters else None,
        )

        logger.debug(f"Found {len(results)} code results")
        return [_transform_code_result(r) for r in results]

    except EmbeddingError as e:
        logger.error(f"Embedding error: {e}")
        raise QueryError("Failed to embed search query", cause=e)
    except VectorStoreError as e:
        logger.error(f"Vector store error: {e}")
        raise QueryError("Failed to search code", cause=e)


async def search_summaries(
    qdrant: QdrantManager,
    embedder: BaseEmbeddingProvider,
    query: str,
    limit: int | None = None,
    project_name: str | None = None,
) -> list[dict]:
    if limit is None:
        limit = QueryConfig.default_search_limit

    if not query or not query.strip():
        raise QueryError("Search query cannot be empty")

    try:
        logger.debug(f"Searching summaries: query='{query}', limit={limit}")
        query_embedding = await embedder.embed(query)

        filters = {}
        if project_name:
            filters["project_name"] = project_name

        results = await qdrant.search(
            collection=CollectionName.SUMMARIES.value,
            query_vector=query_embedding,
            limit=limit,
            filters=filters if filters else None,
        )

        logger.debug(f"Found {len(results)} summary results")
        return [_transform_summary_result(r) for r in results]

    except EmbeddingError as e:
        logger.error(f"Embedding error: {e}")
        raise QueryError("Failed to embed search query", cause=e)
    except VectorStoreError as e:
        logger.error(f"Vector store error: {e}")
        raise QueryError("Failed to search summaries", cause=e)


async def find_similar_code(
    qdrant: QdrantManager,
    embedder: BaseEmbeddingProvider,
    code_snippet: str,
    limit: int | None = None,
    exclude_file: str | None = None,
) -> list[dict]:
    if limit is None:
        limit = QueryConfig.default_search_limit

    exclude_file_buffer = QueryConfig.exclude_file_buffer

    if not code_snippet or not code_snippet.strip():
        raise QueryError("Code snippet cannot be empty")

    try:
        logger.debug(f"Finding similar code: limit={limit}, exclude={exclude_file}")
        query_embedding = await embedder.embed(code_snippet)

        search_limit = limit + exclude_file_buffer if exclude_file else limit
        results = await qdrant.search(
            collection=CollectionName.CODE_CHUNKS.value,
            query_vector=query_embedding,
            limit=search_limit,
        )

        matches = []
        for result in results:
            if exclude_file and result["payload"].get("file_path") == exclude_file:
                continue

            matches.append(_transform_similar_code_result(result))

            if len(matches) >= limit:
                break

        logger.debug(f"Found {len(matches)} similar code results")
        return matches

    except EmbeddingError as e:
        logger.error(f"Embedding error: {e}")
        raise QueryError("Failed to embed code snippet", cause=e)
    except VectorStoreError as e:
        logger.error(f"Vector store error: {e}")
        raise QueryError("Failed to find similar code", cause=e)


class VectorSearcher:
    """Wrapper class for backward compatibility."""

    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: BaseEmbeddingProvider,
    ):
        self.qdrant = qdrant
        self.embedder = embedder

    async def search_code(
        self,
        query: str,
        limit: int | None = None,
        language: str | None = None,
        entity_type: str | None = None,
        project_name: str | None = None,
    ) -> list[dict]:
        return await search_code(
            self.qdrant,
            self.embedder,
            query,
            limit,
            language,
            entity_type,
            project_name,
        )

    async def search_summaries(
        self,
        query: str,
        limit: int | None = None,
        project_name: str | None = None,
    ) -> list[dict]:
        return await search_summaries(
            self.qdrant,
            self.embedder,
            query,
            limit,
            project_name,
        )

    async def find_similar_code(
        self,
        code_snippet: str,
        limit: int | None = None,
        exclude_file: str | None = None,
    ) -> list[dict]:
        return await find_similar_code(
            self.qdrant,
            self.embedder,
            code_snippet,
            limit,
            exclude_file,
        )
