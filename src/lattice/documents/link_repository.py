from uuid import UUID

from lattice.documents.models import DocumentLink, LinkType
from lattice.infrastructure.postgres import PostgresClient


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
