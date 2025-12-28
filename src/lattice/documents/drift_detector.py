import json
import logging
from datetime import datetime

from lattice.documents.models import (
    DocumentChunk,
    DocumentLink,
    DriftAnalysis,
    DriftStatus,
)
from lattice.prompts import get_prompt
from lattice.infrastructure.llm import get_llm_provider
from lattice.shared.config.loader import DriftDetectorConfig

logger = logging.getLogger(__name__)


class DriftDetector:
    def __init__(self):
        self._llm = get_llm_provider()

    async def analyze(
        self,
        doc_chunk: DocumentChunk,
        doc_path: str,
        entity_qualified_name: str,
        entity_type: str,
        file_path: str,
        code_content: str,
        code_hash: str,
        language: str = "python",
    ) -> DriftAnalysis | None:
        try:
            heading_path = doc_chunk.heading_path
            heading_display = " > ".join(heading_path) if heading_path else "Document"

            prompt = get_prompt(
                "documents", "drift_analysis",
                heading_path=heading_display,
                doc_content=doc_chunk.content[:DriftDetectorConfig.doc_content_max],
                entity_name=entity_qualified_name,
                entity_type=entity_type,
                file_path=file_path,
                language=language,
                code_content=code_content[:DriftDetectorConfig.code_content_max],
            )

            response = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=DriftDetectorConfig.max_tokens,
            )

            result = self._parse_response(response)

            if not result.get("relevant", True):
                return None

            severity_map = {
                "none": DriftStatus.ALIGNED,
                "minor": DriftStatus.MINOR_DRIFT,
                "major": DriftStatus.MAJOR_DRIFT,
            }

            drift_severity = severity_map.get(
                result.get("drift_severity", "none"), DriftStatus.ALIGNED
            )
            drift_score = result.get("drift_score", 0.0)

            if not result.get("drift_detected", False):
                drift_severity = DriftStatus.ALIGNED
                drift_score = 0.0

            return DriftAnalysis(
                document_chunk_id=doc_chunk.id,
                document_path=doc_path,
                linked_entity_qualified_name=entity_qualified_name,
                analysis_trigger="manual",
                drift_detected=result.get("drift_detected", False),
                drift_severity=drift_severity,
                drift_score=drift_score,
                issues=result.get("issues", []),
                explanation=result.get("summary", ""),
                doc_excerpt=doc_chunk.content[:DriftDetectorConfig.excerpt_length],
                code_excerpt=code_content[:DriftDetectorConfig.excerpt_length],
                doc_version_hash=doc_chunk.content_hash,
                code_version_hash=code_hash,
                analyzed_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Drift analysis failed for {entity_qualified_name}: {e}")
            return None

    def _parse_response(self, response: str) -> dict:
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse drift analysis response as JSON")
            drift_detected = (
                "drift_detected" in response.lower() and "true" in response.lower()
            )
            return {
                "drift_detected": drift_detected,
                "drift_severity": "unknown",
                "drift_score": DriftDetectorConfig.default_drift_score if drift_detected else 0.0,
                "issues": [],
                "summary": "Could not parse detailed analysis",
            }


class LineRangeCalibrator:
    async def calibrate(
        self,
        link: DocumentLink,
        new_start_line: int,
        new_end_line: int,
        new_code_hash: str,
    ) -> tuple[int | None, int | None, bool]:
        if link.line_range_start is None or link.line_range_end is None:
            return new_start_line, new_end_line, False

        old_length = link.line_range_end - link.line_range_start
        new_length = new_end_line - new_start_line

        if old_length == new_length:
            return new_start_line, new_end_line, False
        else:
            return new_start_line, new_end_line, True
