import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from lattice.documents.chunk_repository import DocumentChunkRepository
from lattice.documents.drift_detector import DriftDetector
from lattice.documents.drift_repository import DriftAnalysisRepository
from lattice.documents.link_repository import DocumentLinkRepository
from lattice.documents.models import (
    DriftAnalysis,
    IndexingProgress,
)
from lattice.documents.repository import DocumentRepository

logger = logging.getLogger(__name__)


async def get_entity_code(
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


async def check_drift(
    project_name: str,
    doc_repo: DocumentRepository,
    chunk_repo: DocumentChunkRepository,
    link_repo: DocumentLinkRepository,
    drift_repo: DriftAnalysisRepository,
    drift_detector: DriftDetector,
    document_path: str | None = None,
    entity_name: str | None = None,
    progress_callback: Callable[[IndexingProgress], None] | None = None,
    max_parallel: int = 1,
    max_retries: int = 5,
    request_delay: float = 0.5,
) -> list[DriftAnalysis]:
    analyses = []

    if progress_callback:
        progress_callback(
            IndexingProgress(
                stage="drift", current=0, total=1, message="Loading documents and chunks..."
            )
        )

    if document_path:
        doc = await doc_repo.get_by_path(project_name, document_path)
        if not doc:
            return []
        chunks = await chunk_repo.get_by_document(doc.id)
    else:
        documents = await doc_repo.list_by_project(project_name)
        chunks = []
        for doc in documents:
            doc_chunks = await chunk_repo.get_by_document(doc.id)
            chunks.extend(doc_chunks)

    if progress_callback:
        progress_callback(
            IndexingProgress(
                stage="drift",
                current=0,
                total=1,
                message=f"Found {len(chunks)} chunks, loading links...",
            )
        )

    all_links = []
    for chunk in chunks:
        links = await link_repo.get_by_chunk(chunk.id)
        if entity_name:
            links = [lnk for lnk in links if lnk.code_entity_qualified_name == entity_name]
        for link in links:
            all_links.append((chunk, link))

    if not all_links:
        if progress_callback:
            progress_callback(
                IndexingProgress(
                    stage="drift", current=1, total=1, message="No links found to analyze"
                )
            )
        return []

    if progress_callback:
        progress_callback(
            IndexingProgress(
                stage="drift",
                current=0,
                total=len(all_links),
                message=f"Analyzing {len(all_links)} doc-code links (parallel={max_parallel})...",
            )
        )

    semaphore = asyncio.Semaphore(max_parallel)
    completed = 0
    skipped = 0
    results_lock = asyncio.Lock()
    entity_analyses: dict[str, DriftAnalysis] = {}

    async def analyze_with_retry(idx: int, chunk, link) -> None:
        nonlocal completed, skipped

        code_content = await get_entity_code(
            link.code_file_path,
            link.line_range_start,
            link.line_range_end,
        )

        if not code_content:
            async with results_lock:
                skipped += 1
                completed += 1
            return

        chunk_doc = await doc_repo.get_by_id(chunk.document_id)
        doc_path = chunk_doc.relative_path if chunk_doc else ""

        analysis = None
        last_error = None

        for attempt in range(max_retries):
            try:
                async with semaphore:
                    analysis = await drift_detector.analyze(
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
                is_rate_limit = (
                    "rate" in error_str
                    or "limit" in error_str
                    or "429" in error_str
                    or "overloaded" in error_str
                )
                if is_rate_limit:
                    wait_time = (2**attempt) * 2 + 5
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
                progress_callback(
                    IndexingProgress(
                        stage="drift",
                        current=completed,
                        total=len(all_links),
                        message=f"Analyzing ({completed}/{len(all_links)})...",
                    )
                )

            if analysis is None:
                skipped += 1
                if last_error:
                    entity_key = link.code_entity_qualified_name
                    logger.warning(f"Skipped {entity_key} after retries: {last_error}")
                return

            entity_key = link.code_entity_qualified_name
            existing = entity_analyses.get(entity_key)
            if existing is None or analysis.drift_score > existing.drift_score:
                entity_analyses[entity_key] = analysis

        await chunk_repo.update_drift(
            chunk.id,
            analysis.drift_severity,
            analysis.drift_score,
        )

    tasks = [analyze_with_retry(idx, chunk, link) for idx, (chunk, link) in enumerate(all_links)]
    await asyncio.gather(*tasks, return_exceptions=True)

    for analysis in entity_analyses.values():
        saved_analysis = await drift_repo.create(analysis)
        analyses.append(saved_analysis)

    if progress_callback:
        progress_callback(
            IndexingProgress(
                stage="drift",
                current=len(all_links),
                total=len(all_links),
                message=f"Complete ({skipped} skipped, {len(analyses)} analyzed)",
            )
        )

    return analyses
