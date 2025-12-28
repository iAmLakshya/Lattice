import logging
from dataclasses import dataclass

from lattice.infrastructure.llm import BaseEmbeddingProvider
from lattice.infrastructure.qdrant.client import CollectionName, QdrantManager
from lattice.shared.exceptions import IndexingError

logger = logging.getLogger(__name__)


@dataclass
class CodeSearchResult:
    score: float
    file_path: str
    entity_type: str
    entity_name: str
    content: str
    start_line: int
    end_line: int


@dataclass
class SummarySearchResult:
    score: float
    file_path: str
    entity_type: str
    entity_name: str
    summary: str


class VectorSearcher:
    def __init__(self, qdrant: QdrantManager, embedder: BaseEmbeddingProvider):
        self.qdrant = qdrant
        self.embedder = embedder

    async def search_code(
        self,
        query: str,
        limit: int = 10,
        language: str | None = None,
        entity_type: str | None = None,
        project_name: str | None = None,
    ) -> list[CodeSearchResult]:
        try:
            query_embedding = await self.embedder.embed(query)

            filters = {}
            if language:
                filters["language"] = language
            if entity_type:
                filters["entity_type"] = entity_type
            if project_name:
                filters["project_name"] = project_name

            results = await self.qdrant.search(
                collection=CollectionName.CODE_CHUNKS.value,
                query_vector=query_embedding,
                limit=limit,
                filters=filters if filters else None,
            )

            return self._format_code_results(results)
        except Exception as e:
            logger.error(f"Code search failed: {e}")
            raise IndexingError(
                f"Failed to search code for query: {query}",
                stage="code_search",
                cause=e,
            )

    async def search_summaries(
        self,
        query: str,
        limit: int = 10,
        entity_type: str | None = None,
    ) -> list[SummarySearchResult]:
        try:
            query_embedding = await self.embedder.embed(query)

            filters = {}
            if entity_type:
                filters["entity_type"] = entity_type

            results = await self.qdrant.search(
                collection=CollectionName.SUMMARIES.value,
                query_vector=query_embedding,
                limit=limit,
                filters=filters if filters else None,
            )

            return self._format_summary_results(results)
        except Exception as e:
            logger.error(f"Summary search failed: {e}")
            raise IndexingError(
                f"Failed to search summaries for query: {query}",
                stage="summary_search",
                cause=e,
            )

    def _format_code_results(self, results: list[dict]) -> list[CodeSearchResult]:
        return [
            CodeSearchResult(
                score=result["score"],
                file_path=result["payload"].get("file_path", ""),
                entity_type=result["payload"].get("entity_type", ""),
                entity_name=result["payload"].get("entity_name", ""),
                content=result["payload"].get("content", ""),
                start_line=result["payload"].get("start_line", 0),
                end_line=result["payload"].get("end_line", 0),
            )
            for result in results
        ]

    def _format_summary_results(self, results: list[dict]) -> list[SummarySearchResult]:
        return [
            SummarySearchResult(
                score=result["score"],
                file_path=result["payload"].get("file_path", ""),
                entity_type=result["payload"].get("entity_type", ""),
                entity_name=result["payload"].get("entity_name", ""),
                summary=result["payload"].get("summary", ""),
            )
            for result in results
        ]
