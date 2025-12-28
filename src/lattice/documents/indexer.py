import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from lattice.documents.models import DocumentChunk
from lattice.infrastructure.qdrant import CollectionName, QdrantManager
from lattice.infrastructure.qdrant.embedder import embed_with_progress
from lattice.infrastructure.llm import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass
class DocumentSearchResult:
    score: float
    chunk_id: str
    document_path: str
    project_name: str
    heading_path: list[str]
    heading_level: int
    content: str
    start_line: int
    end_line: int


class DocumentIndexer:
    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: BaseEmbeddingProvider,
    ):
        self.qdrant = qdrant
        self.embedder = embedder

    async def index_chunks(
        self,
        chunks: list[DocumentChunk],
        document_path: str,
        document_type: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        if not chunks:
            return 0

        texts = [chunk.content for chunk in chunks]
        embeddings = await embed_with_progress(
            self.embedder,
            texts,
            progress_callback=progress_callback,
        )

        ids = [str(uuid.uuid4()) for _ in chunks]
        payloads = [
            chunk.to_qdrant_payload(document_path, document_type) for chunk in chunks
        ]

        await self.qdrant.upsert(
            collection=CollectionName.DOCUMENT_CHUNKS.value,
            ids=ids,
            vectors=embeddings,
            payloads=payloads,
        )

        logger.info(f"Indexed {len(chunks)} document chunks from {document_path}")
        return len(chunks)

    async def delete_document_chunks(self, document_path: str) -> None:
        await self.qdrant.delete(
            CollectionName.DOCUMENT_CHUNKS.value,
            {"document_path": document_path},
        )
        logger.debug(f"Deleted chunks for document: {document_path}")

    async def document_needs_update(
        self, document_path: str, content_hash: str
    ) -> bool:
        return await self.qdrant.file_needs_update(
            CollectionName.DOCUMENT_CHUNKS.value,
            document_path,
            content_hash,
        )


class DocumentSearcher:
    def __init__(self, qdrant: QdrantManager, embedder: BaseEmbeddingProvider):
        self.qdrant = qdrant
        self.embedder = embedder

    async def search(
        self,
        query: str,
        project_name: str | None = None,
        document_type: str | None = None,
        limit: int = 10,
    ) -> list[DocumentSearchResult]:
        query_embedding = await self.embedder.embed(query)

        filters = {}
        if project_name:
            filters["project_name"] = project_name
        if document_type:
            filters["document_type"] = document_type

        results = await self.qdrant.search(
            collection=CollectionName.DOCUMENT_CHUNKS.value,
            query_vector=query_embedding,
            limit=limit,
            filters=filters if filters else None,
        )

        return [
            DocumentSearchResult(
                score=r["score"],
                chunk_id=r["payload"].get("chunk_id", ""),
                document_path=r["payload"].get("document_path", ""),
                project_name=r["payload"].get("project_name", ""),
                heading_path=r["payload"].get("heading_path", []),
                heading_level=r["payload"].get("heading_level", 0),
                content=r["payload"].get("content", ""),
                start_line=r["payload"].get("start_line", 0),
                end_line=r["payload"].get("end_line", 0),
            )
            for r in results
        ]

    async def find_similar_code_chunks(
        self,
        doc_chunk_content: str,
        project_name: str,
        limit: int = 20,
    ) -> list[dict]:
        query_embedding = await self.embedder.embed(doc_chunk_content)

        results = await self.qdrant.search(
            collection=CollectionName.CODE_CHUNKS.value,
            query_vector=query_embedding,
            limit=limit,
            filters={"project_name": project_name},
        )

        return results
