import logging
import uuid
from collections.abc import Callable

from lattice.infrastructure.llm import BaseEmbeddingProvider
from lattice.infrastructure.qdrant.chunker import chunk_file
from lattice.infrastructure.qdrant.client import CollectionName, QdrantManager
from lattice.infrastructure.qdrant.embedder import embed_with_progress
from lattice.parsing.api import ParsedFile
from lattice.shared.exceptions import IndexingError

logger = logging.getLogger(__name__)


class VectorIndexer:
    def __init__(
        self,
        qdrant: QdrantManager,
        embedder: BaseEmbeddingProvider,
    ):
        self.qdrant = qdrant
        self.embedder = embedder

    async def index_file(
        self,
        parsed_file: ParsedFile,
        progress_callback: Callable[[int, int], None] | None = None,
        force: bool = False,
        project_name: str | None = None,
    ) -> int:
        try:
            file_path = str(parsed_file.file_info.path)
            content_hash = parsed_file.file_info.content_hash

            if not force and not await self._needs_indexing(file_path, content_hash):
                logger.debug(f"Skipping unchanged file: {file_path}")
                return 0

            await self.qdrant.delete(
                CollectionName.CODE_CHUNKS.value,
                {"file_path": file_path},
            )

            chunks = chunk_file(parsed_file, project_name=project_name)
            if not chunks:
                logger.debug(f"No chunks generated for file: {file_path}")
                return 0

            texts = [chunk.content for chunk in chunks]
            embeddings = await embed_with_progress(
                self.embedder,
                texts,
                progress_callback=progress_callback,
            )

            ids = [str(uuid.uuid4()) for _ in chunks]
            payloads = [chunk.to_payload() for chunk in chunks]

            await self.qdrant.upsert(
                collection=CollectionName.CODE_CHUNKS.value,
                ids=ids,
                vectors=embeddings,
                payloads=payloads,
            )

            logger.info(f"Indexed {len(chunks)} chunks from {file_path}")
            return len(chunks)
        except Exception as e:
            raise IndexingError(
                f"Failed to index file {parsed_file.file_info.path}",
                stage="file_indexing",
                cause=e,
            )

    async def index_files(
        self,
        parsed_files: list[ParsedFile],
        progress_callback: Callable[[int, int], None] | None = None,
        project_name: str | None = None,
    ) -> int:
        total_chunks = 0

        for i, parsed_file in enumerate(parsed_files):
            try:
                chunks = await self.index_file(parsed_file, project_name=project_name)
                total_chunks += chunks

                if progress_callback:
                    progress_callback(i + 1, len(parsed_files))
            except IndexingError as e:
                logger.error(f"Failed to index file: {e}")
                continue

        logger.info(f"Indexed total of {total_chunks} chunks from {len(parsed_files)} files")
        return total_chunks

    async def index_summary(
        self,
        file_path: str,
        entity_type: str,
        entity_name: str,
        summary: str,
        graph_node_id: str | None = None,
    ) -> None:
        try:
            embedding = await self.embedder.embed(summary)

            payload = {
                "file_path": file_path,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "summary": summary,
                "graph_node_id": graph_node_id,
            }

            await self.qdrant.upsert(
                collection=CollectionName.SUMMARIES.value,
                ids=[str(uuid.uuid4())],
                vectors=[embedding],
                payloads=[payload],
            )

            logger.info(f"Indexed summary for {entity_name} in {file_path}")
        except Exception as e:
            raise IndexingError(
                f"Failed to index summary for {entity_name}",
                stage="summary_indexing",
                cause=e,
            )

    async def _needs_indexing(self, file_path: str, content_hash: str) -> bool:
        return await self.qdrant.file_needs_update(
            CollectionName.CODE_CHUNKS.value,
            file_path,
            content_hash,
        )
