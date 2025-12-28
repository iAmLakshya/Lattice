import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from lattice.documents.chunk_repository import DocumentChunkRepository
from lattice.documents.chunker import DocumentChunker
from lattice.documents.indexer import DocumentIndexer
from lattice.documents.link_finder import AILinkFinder
from lattice.documents.link_repository import DocumentLinkRepository
from lattice.documents.models import (
    Document,
    IndexingProgress,
    IndexingResult,
)
from lattice.documents.operations.link import establish_links, get_known_entities
from lattice.documents.reference_extractor import ReferenceExtractor
from lattice.documents.repository import DocumentRepository
from lattice.documents.scanner import DocumentScanner
from lattice.infrastructure.memgraph import DocumentQueries, MemgraphClient

logger = logging.getLogger(__name__)


def extract_title(content: str) -> str | None:
    lines = content.split("\n")
    for line in lines[:20]:
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


async def index_documents(
    path: str | Path,
    project_name: str,
    doc_repo: DocumentRepository,
    chunk_repo: DocumentChunkRepository,
    link_repo: DocumentLinkRepository,
    chunker: DocumentChunker,
    indexer: DocumentIndexer,
    reference_extractor: ReferenceExtractor,
    link_finder: AILinkFinder,
    memgraph: MemgraphClient | None = None,
    document_type: str = "markdown",
    force: bool = False,
    progress_callback: Callable[[IndexingProgress], None] | None = None,
) -> IndexingResult:
    start_time = datetime.now()
    scanner = DocumentScanner(path)
    doc_infos = scanner.scan_all()

    if not doc_infos:
        return IndexingResult(
            documents_indexed=0,
            chunks_created=0,
            links_established=0,
            elapsed_seconds=0.0,
        )

    documents_indexed = 0
    total_chunks = 0
    total_links = 0

    for i, doc_info in enumerate(doc_infos):
        if progress_callback:
            progress_callback(
                IndexingProgress(
                    stage="indexing",
                    current=i + 1,
                    total=len(doc_infos),
                    message=f"Processing {doc_info.relative_path}",
                )
            )

        if not force:
            needs_update = await indexer.document_needs_update(
                str(doc_info.path), doc_info.content_hash
            )
            if not needs_update:
                logger.debug(f"Skipping unchanged document: {doc_info.relative_path}")
                continue

        content = doc_info.path.read_text(encoding="utf-8")
        title = extract_title(content)

        doc = Document(
            project_name=project_name,
            file_path=str(doc_info.path),
            relative_path=doc_info.relative_path,
            title=title,
            document_type=document_type,
            content_hash=doc_info.content_hash,
            indexed_at=datetime.now(),
        )

        saved_doc = await doc_repo.upsert(doc)

        await chunk_repo.delete_by_document(saved_doc.id)
        await indexer.delete_document_chunks(str(doc_info.path))

        chunks = chunker.chunk_document(
            content=content,
            document_id=saved_doc.id,
            project_name=project_name,
        )

        if chunks:
            await chunk_repo.create_batch(chunks)
            await indexer.index_chunks(
                chunks=chunks,
                document_path=str(doc_info.path),
                document_type=document_type,
            )
            total_chunks += len(chunks)

        saved_doc.chunk_count = len(chunks)
        await doc_repo.upsert(saved_doc)

        if memgraph:
            await memgraph.execute(
                DocumentQueries.CREATE_DOCUMENT,
                {
                    "file_path": str(doc_info.path),
                    "relative_path": doc_info.relative_path,
                    "project_name": project_name,
                    "title": title,
                    "document_type": document_type,
                    "content_hash": doc_info.content_hash,
                    "chunk_count": len(chunks),
                    "drift_status": "unknown",
                    "drift_score": None,
                },
            )

        documents_indexed += 1

    if documents_indexed > 0:
        if progress_callback:
            progress_callback(
                IndexingProgress(
                    stage="linking",
                    current=0,
                    total=1,
                    message="Establishing doc-code links...",
                )
            )

        known_entities = await get_known_entities(project_name, memgraph)
        if known_entities:
            total_links = await establish_links(
                project_name=project_name,
                doc_repo=doc_repo,
                chunk_repo=chunk_repo,
                link_repo=link_repo,
                reference_extractor=reference_extractor,
                link_finder=link_finder,
                memgraph=memgraph,
                known_entities=known_entities,
                progress_callback=progress_callback,
            )

    elapsed = (datetime.now() - start_time).total_seconds()

    return IndexingResult(
        documents_indexed=documents_indexed,
        chunks_created=total_chunks,
        links_established=total_links,
        elapsed_seconds=elapsed,
    )
