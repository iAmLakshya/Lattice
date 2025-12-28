from uuid import UUID

from lattice.documents.models import DocumentChunk, DriftStatus
from lattice.infrastructure.postgres import PostgresClient


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
