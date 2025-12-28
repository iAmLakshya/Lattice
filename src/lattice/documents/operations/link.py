import logging
from collections.abc import Callable

from lattice.documents.chunk_repository import DocumentChunkRepository
from lattice.documents.link_finder import AILinkFinder
from lattice.documents.link_repository import DocumentLinkRepository
from lattice.documents.models import (
    DocumentLink,
    IndexingProgress,
    LinkType,
)
from lattice.documents.reference_extractor import ReferenceExtractor
from lattice.documents.repository import DocumentRepository
from lattice.infrastructure.memgraph import EntityQueries, MemgraphClient

logger = logging.getLogger(__name__)


async def get_entity_details(
    project_name: str,
    memgraph: MemgraphClient | None,
) -> dict[str, dict]:
    if not memgraph:
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
        results = await memgraph.execute(query, {"project_id": project_id})
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


async def get_known_entities(
    project_name: str,
    memgraph: MemgraphClient | None,
) -> set[str]:
    if not memgraph:
        return set()

    project_id = project_name

    try:
        await memgraph.execute(EntityQueries.BACKFILL_PROJECT_ID, {})

        query = """
        MATCH (n)
        WHERE (n:Function OR n:Class OR n:Method)
          AND n.project_id = $project_id
        RETURN n.qualified_name as name
        """
        results = await memgraph.execute(query, {"project_id": project_id})
        entities = {r["name"] for r in results if r.get("name")}
        logger.info(f"Found {len(entities)} code entities for project {project_name}")
        return entities
    except Exception as e:
        logger.warning(f"Failed to get known entities: {e}")
        return set()


async def establish_links(
    project_name: str,
    doc_repo: DocumentRepository,
    chunk_repo: DocumentChunkRepository,
    link_repo: DocumentLinkRepository,
    reference_extractor: ReferenceExtractor,
    link_finder: AILinkFinder,
    memgraph: MemgraphClient | None = None,
    known_entities: set[str] | None = None,
    progress_callback: Callable[[IndexingProgress], None] | None = None,
) -> int:
    entity_details = await get_entity_details(project_name, memgraph)
    documents = await doc_repo.list_by_project(project_name)
    total_links = 0

    for doc_idx, doc in enumerate(documents):
        chunks = await chunk_repo.get_by_document(doc.id)

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
                explicit_refs = reference_extractor.extract(chunk.content, known_entities)

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
                    await link_repo.create(link)
                    total_links += 1

            implicit_links = await link_finder.find_links(chunk)

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
                await link_repo.create(link)
                total_links += 1

        doc.link_count = total_links
        await doc_repo.upsert(doc)

    return total_links
