import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lattice.database.postgres import PostgresClient
from lattice.documents.chunker import DocumentChunker
from lattice.documents.drift_detector import DriftDetector
from lattice.documents.indexer import DocumentIndexer, DocumentSearcher
from lattice.documents.link_finder import AILinkFinder
from lattice.documents.models import (
    Document,
    DocumentLink,
    DriftAnalysis,
    LinkType,
)
from lattice.documents.reference_extractor import ReferenceExtractor
from lattice.documents.repository import (
    DocumentChunkRepository,
    DocumentLinkRepository,
    DocumentRepository,
    DriftAnalysisRepository,
)
from lattice.documents.scanner import DocumentScanner
from lattice.embeddings.client import QdrantManager
from lattice.embeddings.embedder import Embedder
from lattice.graph.client import MemgraphClient
from lattice.graph.queries import DocumentQueries

logger = logging.getLogger(__name__)


@dataclass
class IndexingProgress:
    stage: str
    current: int
    total: int
    message: str


@dataclass
class IndexingResult:
    documents_indexed: int
    chunks_created: int
    links_established: int
    elapsed_seconds: float


class DocumentService:
    def __init__(
        self,
        postgres: PostgresClient,
        qdrant: QdrantManager,
        embedder: Embedder,
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
                needs_update = await self._indexer.document_needs_update(
                    str(doc_info.path), doc_info.content_hash
                )
                if not needs_update:
                    logger.debug(f"Skipping unchanged document: {doc_info.relative_path}")
                    continue

            content = doc_info.path.read_text(encoding="utf-8")
            title = self._extract_title(content)

            doc = Document(
                project_name=project_name,
                file_path=str(doc_info.path),
                relative_path=doc_info.relative_path,
                title=title,
                document_type=document_type,
                content_hash=doc_info.content_hash,
                indexed_at=datetime.now(),
            )

            saved_doc = await self._doc_repo.upsert(doc)

            await self._chunk_repo.delete_by_document(saved_doc.id)
            await self._indexer.delete_document_chunks(str(doc_info.path))

            chunks = self._chunker.chunk_document(
                content=content,
                document_id=saved_doc.id,
                project_name=project_name,
            )

            if chunks:
                await self._chunk_repo.create_batch(chunks)
                await self._indexer.index_chunks(
                    chunks=chunks,
                    document_path=str(doc_info.path),
                    document_type=document_type,
                )
                total_chunks += len(chunks)

            saved_doc.chunk_count = len(chunks)
            await self._doc_repo.upsert(saved_doc)

            if self._memgraph:
                await self._memgraph.execute(
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

            known_entities = await self._get_known_entities(project_name)
            if known_entities:
                total_links = await self.establish_links(
                    project_name=project_name,
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

    async def establish_links(
        self,
        project_name: str,
        known_entities: set[str] | None = None,
        progress_callback: Callable[[IndexingProgress], None] | None = None,
    ) -> int:
        entity_details = await self._get_entity_details(project_name)
        documents = await self._doc_repo.list_by_project(project_name)
        total_links = 0

        for doc_idx, doc in enumerate(documents):
            chunks = await self._chunk_repo.get_by_document(doc.id)

            for chunk_idx, chunk in enumerate(chunks):
                if progress_callback:
                    progress_callback(
                        IndexingProgress(
                            stage="linking",
                            current=doc_idx * 100 + chunk_idx,
                            total=len(documents) * 100,
                            message=f"Finding links for {doc.relative_path}",
                        )
                    )

                if known_entities:
                    explicit_refs = self._reference_extractor.extract(
                        chunk.content, known_entities
                    )

                    for ref in explicit_refs:
                        details = entity_details.get(ref.entity_qualified_name, {})
                        link = DocumentLink(
                            document_chunk_id=chunk.id,
                            code_entity_qualified_name=ref.entity_qualified_name,
                            code_entity_type=details.get("type", "unknown"),
                            code_file_path=details.get("file_path", ""),
                            link_type=LinkType.EXPLICIT,
                            confidence_score=ref.confidence,
                            reasoning=f"Found via {ref.pattern_type} pattern",
                            line_range_start=details.get("start_line"),
                            line_range_end=details.get("end_line"),
                        )
                        await self._link_repo.create(link)
                        total_links += 1

                implicit_links = await self._link_finder.find_links(chunk)

                for impl_link in implicit_links:
                    details = entity_details.get(impl_link.entity_qualified_name, {})
                    link = DocumentLink(
                        document_chunk_id=chunk.id,
                        code_entity_qualified_name=impl_link.entity_qualified_name,
                        code_entity_type=impl_link.entity_type or details.get("type", "unknown"),
                        code_file_path=details.get("file_path", ""),
                        link_type=LinkType.IMPLICIT,
                        confidence_score=impl_link.confidence,
                        reasoning=impl_link.reasoning,
                        line_range_start=details.get("start_line"),
                        line_range_end=details.get("end_line"),
                    )
                    await self._link_repo.create(link)
                    total_links += 1

            doc.link_count = total_links
            await self._doc_repo.upsert(doc)

        return total_links

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
        analyses = []

        if progress_callback:
            progress_callback(IndexingProgress(
                stage="drift", current=0, total=1,
                message="Loading documents and chunks..."
            ))

        if document_path:
            doc = await self._doc_repo.get_by_path(project_name, document_path)
            if not doc:
                return []
            chunks = await self._chunk_repo.get_by_document(doc.id)
        else:
            documents = await self._doc_repo.list_by_project(project_name)
            chunks = []
            for doc in documents:
                doc_chunks = await self._chunk_repo.get_by_document(doc.id)
                chunks.extend(doc_chunks)

        if progress_callback:
            progress_callback(IndexingProgress(
                stage="drift", current=0, total=1,
                message=f"Found {len(chunks)} chunks, loading links..."
            ))

        all_links = []
        for chunk in chunks:
            links = await self._link_repo.get_by_chunk(chunk.id)
            if entity_name:
                links = [
                    lnk for lnk in links
                    if lnk.code_entity_qualified_name == entity_name
                ]
            for link in links:
                all_links.append((chunk, link))

        if not all_links:
            if progress_callback:
                progress_callback(IndexingProgress(
                    stage="drift", current=1, total=1,
                    message="No links found to analyze"
                ))
            return []

        if progress_callback:
            progress_callback(IndexingProgress(
                stage="drift", current=0, total=len(all_links),
                message=f"Analyzing {len(all_links)} doc-code links (parallel={max_parallel})..."
            ))

        semaphore = asyncio.Semaphore(max_parallel)
        completed = 0
        skipped = 0
        results_lock = asyncio.Lock()
        entity_analyses: dict[str, DriftAnalysis] = {}

        async def analyze_with_retry(idx: int, chunk, link) -> None:
            nonlocal completed, skipped

            code_content = await self._get_entity_code(
                link.code_file_path,
                link.line_range_start,
                link.line_range_end,
            )

            if not code_content:
                async with results_lock:
                    skipped += 1
                    completed += 1
                return

            chunk_doc = await self._doc_repo.get_by_id(chunk.document_id)
            doc_path = chunk_doc.relative_path if chunk_doc else ""

            analysis = None
            last_error = None

            for attempt in range(max_retries):
                try:
                    async with semaphore:
                        analysis = await self._drift_detector.analyze(
                            doc_chunk=chunk,
                            doc_path=doc_path,
                            entity_qualified_name=link.code_entity_qualified_name,
                            entity_type=link.code_entity_type,
                            file_path=link.code_file_path,
                            code_content=code_content,
                            code_hash=link.code_version_hash or "",
                        )
                        if request_delay > 0:
                            await asyncio.sleep(request_delay)
                    break
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    if "rate" in error_str or "limit" in error_str or "429" in error_str or "overloaded" in error_str:
                        wait_time = (2 ** attempt) * 2 + 5
                        logger.warning(
                            f"Rate limit hit for {link.code_entity_qualified_name}, "
                            f"retry {attempt + 1}/{max_retries} in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Analysis failed for {link.code_entity_qualified_name}: {e}")
                        break

            async with results_lock:
                completed += 1
                if progress_callback:
                    progress_callback(IndexingProgress(
                        stage="drift", current=completed, total=len(all_links),
                        message=f"Analyzing ({completed}/{len(all_links)})..."
                    ))

                if analysis is None:
                    skipped += 1
                    if last_error:
                        logger.warning(f"Skipped {link.code_entity_qualified_name} after retries: {last_error}")
                    return

                entity_key = link.code_entity_qualified_name
                existing = entity_analyses.get(entity_key)
                if existing is None or analysis.drift_score > existing.drift_score:
                    entity_analyses[entity_key] = analysis

            await self._chunk_repo.update_drift(
                chunk.id,
                analysis.drift_severity,
                analysis.drift_score,
            )

        tasks = [
            analyze_with_retry(idx, chunk, link)
            for idx, (chunk, link) in enumerate(all_links)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        for analysis in entity_analyses.values():
            saved_analysis = await self._drift_repo.create(analysis)
            analyses.append(saved_analysis)

        if progress_callback:
            progress_callback(IndexingProgress(
                stage="drift", current=len(all_links), total=len(all_links),
                message=f"Complete ({skipped} skipped, {len(analyses)} analyzed)"
            ))

        return analyses

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
        return await self._searcher.search(
            query=query,
            project_name=project_name,
            limit=limit,
        )

    def _extract_title(self, content: str) -> str | None:
        lines = content.split("\n")
        for line in lines[:20]:
            match = re.match(r"^#\s+(.+)$", line.strip())
            if match:
                return match.group(1).strip()
        return None

    async def _get_entity_code(
        self,
        file_path: str,
        start_line: int | None,
        end_line: int | None,
    ) -> str:
        try:
            path = Path(file_path)
            if not path.exists():
                return ""

            content = path.read_text(encoding="utf-8")

            if start_line and end_line:
                lines = content.split("\n")
                return "\n".join(lines[start_line - 1 : end_line])

            return content
        except Exception:
            return ""

    async def _get_entity_details(self, project_name: str) -> dict[str, dict]:
        if not self._memgraph:
            return {}

        project_id = project_name

        try:
            query = """
            MATCH (n)
            WHERE (n:Function OR n:Class OR n:Method)
              AND n.project_id = $project_id
            RETURN n.qualified_name as name,
                   labels(n)[0] as type,
                   n.file_path as file_path,
                   n.start_line as start_line,
                   n.end_line as end_line
            """
            results = await self._memgraph.execute(query, {"project_id": project_id})
            return {
                r["name"]: {
                    "type": r["type"],
                    "file_path": r["file_path"],
                    "start_line": r["start_line"],
                    "end_line": r["end_line"],
                }
                for r in results
                if r.get("name")
            }
        except Exception as e:
            logger.warning(f"Failed to get entity details: {e}")
            return {}

    async def _get_known_entities(self, project_name: str) -> set[str]:
        if not self._memgraph:
            return set()

        project_id = project_name

        try:
            from lattice.graph.queries import EntityQueries
            await self._memgraph.execute(EntityQueries.BACKFILL_PROJECT_ID, {})

            query = """
            MATCH (n)
            WHERE (n:Function OR n:Class OR n:Method)
              AND n.project_id = $project_id
            RETURN n.qualified_name as name
            """
            results = await self._memgraph.execute(query, {"project_id": project_id})
            entities = {r["name"] for r in results if r.get("name")}
            logger.info(f"Found {len(entities)} code entities for project {project_name}")
            return entities
        except Exception as e:
            logger.warning(f"Failed to get known entities: {e}")
            return set()
