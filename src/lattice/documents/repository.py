import logging
from uuid import UUID

from lattice.documents.models import Document, DriftStatus
from lattice.infrastructure.postgres import PostgresClient

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
