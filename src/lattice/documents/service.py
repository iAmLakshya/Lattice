from collections.abc import Callable
from pathlib import Path

from lattice.infrastructure.postgres.postgres import PostgresClient
from lattice.documents.chunker import DocumentChunker
from lattice.documents.drift_detector import DriftDetector
from lattice.documents.indexer import DocumentIndexer, DocumentSearcher
from lattice.documents.link_finder import AILinkFinder
from lattice.documents.models import (
    Document,
    DocumentLink,
    DriftAnalysis,
    IndexingProgress,
    IndexingResult,
)
from lattice.documents.reference_extractor import ReferenceExtractor
from lattice.documents.repository import (
    DocumentChunkRepository,
    DocumentLinkRepository,
    DocumentRepository,
    DriftAnalysisRepository,
)
from lattice.infrastructure.qdrant import QdrantManager
from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.infrastructure.llm import BaseEmbeddingProvider


class DocumentService:
    def __init__(
        self,
        postgres: PostgresClient,
        qdrant: QdrantManager,
        embedder: BaseEmbeddingProvider,
        memgraph: MemgraphClient | None = None,
    ):
        self._postgres = postgres
        self._qdrant = qdrant
        self._embedder = embedder
        self._memgraph = memgraph

        self._doc_repo = DocumentRepository(postgres)
        self._chunk_repo = DocumentChunkRepository(postgres)
        self._link_repo = DocumentLinkRepository(postgres)
        self._drift_repo = DriftAnalysisRepository(postgres)

        self._chunker = DocumentChunker()
        self._indexer = DocumentIndexer(qdrant, embedder)
        self._searcher = DocumentSearcher(qdrant, embedder)
        self._reference_extractor = ReferenceExtractor()
        self._link_finder = AILinkFinder(qdrant, embedder)
        self._drift_detector = DriftDetector()

    async def index_documents(
        self,
        path: str | Path,
        project_name: str,
        document_type: str = "markdown",
        force: bool = False,
        progress_callback: Callable[[IndexingProgress], None] | None = None,
    ) -> IndexingResult:
        from lattice.documents.operations.index import index_documents

        return await index_documents(
            path=path,
            project_name=project_name,
            doc_repo=self._doc_repo,
            chunk_repo=self._chunk_repo,
            link_repo=self._link_repo,
            chunker=self._chunker,
            indexer=self._indexer,
            reference_extractor=self._reference_extractor,
            link_finder=self._link_finder,
            memgraph=self._memgraph,
            document_type=document_type,
            force=force,
            progress_callback=progress_callback,
        )

    async def establish_links(
        self,
        project_name: str,
        known_entities: set[str] | None = None,
        progress_callback: Callable[[IndexingProgress], None] | None = None,
    ) -> int:
        from lattice.documents.operations.link import establish_links

        return await establish_links(
            project_name=project_name,
            doc_repo=self._doc_repo,
            chunk_repo=self._chunk_repo,
            link_repo=self._link_repo,
            reference_extractor=self._reference_extractor,
            link_finder=self._link_finder,
            memgraph=self._memgraph,
            known_entities=known_entities,
            progress_callback=progress_callback,
        )

    async def check_drift(
        self,
        project_name: str,
        document_path: str | None = None,
        entity_name: str | None = None,
        progress_callback: Callable[[IndexingProgress], None] | None = None,
        max_parallel: int = 1,
        max_retries: int = 5,
        request_delay: float = 0.5,
    ) -> list[DriftAnalysis]:
        from lattice.documents.operations.drift import check_drift

        return await check_drift(
            project_name=project_name,
            doc_repo=self._doc_repo,
            chunk_repo=self._chunk_repo,
            link_repo=self._link_repo,
            drift_repo=self._drift_repo,
            drift_detector=self._drift_detector,
            document_path=document_path,
            entity_name=entity_name,
            progress_callback=progress_callback,
            max_parallel=max_parallel,
            max_retries=max_retries,
            request_delay=request_delay,
        )

    async def list_documents(self, project_name: str) -> list[Document]:
        return await self._doc_repo.list_by_project(project_name)

    async def list_drifted_documents(self, project_name: str) -> list[Document]:
        return await self._doc_repo.list_drifted(project_name)

    async def get_document_links(
        self, document_path: str | None = None, entity_name: str | None = None
    ) -> list[DocumentLink]:
        if entity_name:
            return await self._link_repo.get_by_entity(entity_name)
        return []

    async def search_documents(
        self,
        query: str,
        project_name: str | None = None,
        limit: int = 10,
    ):
        from lattice.documents.operations.search import search_documents

        return await search_documents(
            query=query,
            searcher=self._searcher,
            project_name=project_name,
            limit=limit,
        )
