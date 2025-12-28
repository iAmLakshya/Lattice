import json
from uuid import UUID

from lattice.documents.models import DriftAnalysis, DriftStatus
from lattice.infrastructure.postgres import PostgresClient


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
