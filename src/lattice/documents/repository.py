import json
import logging
from uuid import UUID

from lattice.database.postgres import PostgresClient
from lattice.documents.models import (
    Document,
    DocumentChunk,
    DocumentLink,
    DriftAnalysis,
    DriftStatus,
    LinkType,
)

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, postgres: PostgresClient):
        self._postgres = postgres

    async def upsert(self, document: Document) -> Document:
        query = """
            INSERT INTO documents (
                project_name, file_path, relative_path, title,
                document_type, content_hash, chunk_count, link_count,
                drift_status, drift_score, indexed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (project_name, file_path) DO UPDATE SET
                relative_path = EXCLUDED.relative_path,
                title = EXCLUDED.title,
                document_type = EXCLUDED.document_type,
                content_hash = EXCLUDED.content_hash,
                chunk_count = EXCLUDED.chunk_count,
                link_count = EXCLUDED.link_count,
                drift_status = EXCLUDED.drift_status,
                drift_score = EXCLUDED.drift_score,
                indexed_at = EXCLUDED.indexed_at,
                updated_at = NOW()
            RETURNING *
        """
        row = await self._postgres.fetchrow(
            query,
            document.project_name,
            document.file_path,
            document.relative_path,
            document.title,
            document.document_type,
            document.content_hash,
            document.chunk_count,
            document.link_count,
            document.drift_status.value,
            document.drift_score,
            document.indexed_at,
        )
        return self._row_to_document(row)

    async def get_by_path(self, project_name: str, file_path: str) -> Document | None:
        query = "SELECT * FROM documents WHERE project_name = $1 AND file_path = $2"
        row = await self._postgres.fetchrow(query, project_name, file_path)
        return self._row_to_document(row) if row else None

    async def get_by_id(self, document_id: UUID) -> Document | None:
        query = "SELECT * FROM documents WHERE id = $1"
        row = await self._postgres.fetchrow(query, document_id)
        return self._row_to_document(row) if row else None

    async def list_by_project(self, project_name: str) -> list[Document]:
        query = "SELECT * FROM documents WHERE project_name = $1 ORDER BY file_path"
        rows = await self._postgres.fetch(query, project_name)
        return [self._row_to_document(row) for row in rows]

    async def list_drifted(self, project_name: str) -> list[Document]:
        query = """
            SELECT * FROM documents
            WHERE project_name = $1 AND drift_status IN ('minor_drift', 'major_drift')
            ORDER BY drift_score DESC
        """
        rows = await self._postgres.fetch(query, project_name)
        return [self._row_to_document(row) for row in rows]

    async def delete(self, project_name: str, file_path: str) -> bool:
        query = "DELETE FROM documents WHERE project_name = $1 AND file_path = $2"
        result = await self._postgres.execute(query, project_name, file_path)
        return result == "DELETE 1"

    async def update_drift(
        self,
        document_id: UUID,
        drift_status: DriftStatus,
        drift_score: float | None,
    ) -> None:
        query = """
            UPDATE documents
            SET drift_status = $2, drift_score = $3, last_drift_check_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """
        await self._postgres.execute(query, document_id, drift_status.value, drift_score)

    def _row_to_document(self, row) -> Document:
        return Document(
            id=row["id"],
            project_name=row["project_name"],
            file_path=row["file_path"],
            relative_path=row["relative_path"],
            title=row["title"],
            document_type=row["document_type"],
            content_hash=row["content_hash"],
            chunk_count=row["chunk_count"],
            link_count=row["link_count"],
            drift_status=DriftStatus(row["drift_status"]),
            drift_score=row["drift_score"],
            indexed_at=row["indexed_at"],
            last_drift_check_at=row["last_drift_check_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class DocumentChunkRepository:
    def __init__(self, postgres: PostgresClient):
        self._postgres = postgres

    async def create(self, chunk: DocumentChunk) -> DocumentChunk:
        query = """
            INSERT INTO document_chunks (
                id, document_id, project_name, content, heading_path,
                heading_level, start_line, end_line, content_hash,
                embedding_id, explicit_references
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """
        row = await self._postgres.fetchrow(
            query,
            chunk.id,
            chunk.document_id,
            chunk.project_name,
            chunk.content,
            chunk.heading_path,
            chunk.heading_level,
            chunk.start_line,
            chunk.end_line,
            chunk.content_hash,
            chunk.embedding_id,
            chunk.explicit_references,
        )
        return self._row_to_chunk(row)

    async def create_batch(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        query = """
            INSERT INTO document_chunks (
                id, document_id, project_name, content, heading_path,
                heading_level, start_line, end_line, content_hash,
                embedding_id, explicit_references
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """
        async with self._postgres.acquire() as conn:
            for chunk in chunks:
                await conn.execute(
                    query,
                    chunk.id,
                    chunk.document_id,
                    chunk.project_name,
                    chunk.content,
                    chunk.heading_path,
                    chunk.heading_level,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.content_hash,
                    chunk.embedding_id,
                    chunk.explicit_references,
                )
        return len(chunks)

    async def get_by_document(self, document_id: UUID) -> list[DocumentChunk]:
        query = "SELECT * FROM document_chunks WHERE document_id = $1 ORDER BY start_line"
        rows = await self._postgres.fetch(query, document_id)
        return [self._row_to_chunk(row) for row in rows]

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk | None:
        query = "SELECT * FROM document_chunks WHERE id = $1"
        row = await self._postgres.fetchrow(query, chunk_id)
        return self._row_to_chunk(row) if row else None

    async def delete_by_document(self, document_id: UUID) -> int:
        query = "DELETE FROM document_chunks WHERE document_id = $1"
        result = await self._postgres.execute(query, document_id)
        return int(result.split()[-1]) if result else 0

    async def update_drift(
        self,
        chunk_id: UUID,
        drift_status: DriftStatus,
        drift_score: float | None,
    ) -> None:
        query = """
            UPDATE document_chunks
            SET drift_status = $2, drift_score = $3, last_drift_check_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """
        await self._postgres.execute(query, chunk_id, drift_status.value, drift_score)

    def _row_to_chunk(self, row) -> DocumentChunk:
        return DocumentChunk(
            id=row["id"],
            document_id=row["document_id"],
            project_name=row["project_name"],
            content=row["content"],
            heading_path=list(row["heading_path"]) if row["heading_path"] else [],
            heading_level=row["heading_level"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            content_hash=row["content_hash"],
            embedding_id=row["embedding_id"],
            explicit_references=(
                list(row["explicit_references"]) if row["explicit_references"] else []
            ),
            drift_status=DriftStatus(row["drift_status"]),
            drift_score=row["drift_score"],
            last_drift_check_at=row["last_drift_check_at"],
        )


class DocumentLinkRepository:
    def __init__(self, postgres: PostgresClient):
        self._postgres = postgres

    async def create(self, link: DocumentLink) -> DocumentLink:
        query = """
            INSERT INTO document_links (
                document_chunk_id, code_entity_qualified_name, code_entity_type,
                code_file_path, link_type, confidence_score,
                line_range_start, line_range_end, code_version_hash, reasoning
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        """
        row = await self._postgres.fetchrow(
            query,
            link.document_chunk_id,
            link.code_entity_qualified_name,
            link.code_entity_type,
            link.code_file_path,
            link.link_type.value,
            link.confidence_score,
            link.line_range_start,
            link.line_range_end,
            link.code_version_hash,
            link.reasoning,
        )
        return self._row_to_link(row)

    async def get_by_chunk(self, chunk_id: UUID) -> list[DocumentLink]:
        query = """
            SELECT * FROM document_links
            WHERE document_chunk_id = $1
            ORDER BY confidence_score DESC
        """
        rows = await self._postgres.fetch(query, chunk_id)
        return [self._row_to_link(row) for row in rows]

    async def get_by_entity(self, entity_qualified_name: str) -> list[DocumentLink]:
        query = """
            SELECT * FROM document_links
            WHERE code_entity_qualified_name = $1
            ORDER BY confidence_score DESC
        """
        rows = await self._postgres.fetch(query, entity_qualified_name)
        return [self._row_to_link(row) for row in rows]

    async def delete_by_chunk(self, chunk_id: UUID) -> int:
        query = "DELETE FROM document_links WHERE document_chunk_id = $1"
        result = await self._postgres.execute(query, chunk_id)
        return int(result.split()[-1]) if result else 0

    async def update_line_range(
        self,
        link_id: UUID,
        line_start: int,
        line_end: int,
        code_hash: str,
    ) -> None:
        query = """
            UPDATE document_links
            SET line_range_start = $2, line_range_end = $3,
                code_version_hash = $4, last_calibrated_at = NOW()
            WHERE id = $1
        """
        await self._postgres.execute(query, link_id, line_start, line_end, code_hash)

    def _row_to_link(self, row) -> DocumentLink:
        return DocumentLink(
            id=row["id"],
            document_chunk_id=row["document_chunk_id"],
            code_entity_qualified_name=row["code_entity_qualified_name"],
            code_entity_type=row["code_entity_type"],
            code_file_path=row["code_file_path"],
            link_type=LinkType(row["link_type"]),
            confidence_score=row["confidence_score"],
            line_range_start=row["line_range_start"],
            line_range_end=row["line_range_end"],
            code_version_hash=row["code_version_hash"],
            reasoning=row["reasoning"],
            created_at=row["created_at"],
            last_calibrated_at=row["last_calibrated_at"],
        )


class DriftAnalysisRepository:
    def __init__(self, postgres: PostgresClient):
        self._postgres = postgres

    async def create(self, analysis: DriftAnalysis) -> DriftAnalysis:
        query = """
            INSERT INTO drift_analyses (
                document_chunk_id, document_path, linked_entity_qualified_name,
                analysis_trigger, drift_detected, drift_severity, drift_score,
                issues, explanation, doc_excerpt, code_excerpt,
                doc_version_hash, code_version_hash, analyzed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING *
        """
        row = await self._postgres.fetchrow(
            query,
            analysis.document_chunk_id,
            analysis.document_path,
            analysis.linked_entity_qualified_name,
            analysis.analysis_trigger,
            analysis.drift_detected,
            analysis.drift_severity.value,
            analysis.drift_score,
            json.dumps(analysis.issues),
            analysis.explanation,
            analysis.doc_excerpt,
            analysis.code_excerpt,
            analysis.doc_version_hash,
            analysis.code_version_hash,
            analysis.analyzed_at,
        )
        return self._row_to_analysis(row)

    async def get_latest_by_chunk(self, chunk_id: UUID) -> DriftAnalysis | None:
        query = """
            SELECT * FROM drift_analyses
            WHERE document_chunk_id = $1
            ORDER BY analyzed_at DESC LIMIT 1
        """
        row = await self._postgres.fetchrow(query, chunk_id)
        return self._row_to_analysis(row) if row else None

    async def get_history(self, chunk_id: UUID, limit: int = 10) -> list[DriftAnalysis]:
        query = """
            SELECT * FROM drift_analyses
            WHERE document_chunk_id = $1
            ORDER BY analyzed_at DESC LIMIT $2
        """
        rows = await self._postgres.fetch(query, chunk_id, limit)
        return [self._row_to_analysis(row) for row in rows]

    def _row_to_analysis(self, row) -> DriftAnalysis:
        issues = row["issues"]
        if isinstance(issues, str):
            issues = json.loads(issues)

        return DriftAnalysis(
            id=row["id"],
            document_chunk_id=row["document_chunk_id"],
            document_path=row["document_path"],
            linked_entity_qualified_name=row["linked_entity_qualified_name"],
            analysis_trigger=row["analysis_trigger"],
            drift_detected=row["drift_detected"],
            drift_severity=DriftStatus(row["drift_severity"]),
            drift_score=row["drift_score"],
            issues=issues,
            explanation=row["explanation"],
            doc_excerpt=row["doc_excerpt"],
            code_excerpt=row["code_excerpt"],
            doc_version_hash=row["doc_version_hash"],
            code_version_hash=row["code_version_hash"],
            analyzed_at=row["analyzed_at"],
        )
