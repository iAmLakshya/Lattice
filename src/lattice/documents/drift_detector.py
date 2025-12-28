import json
import logging
from datetime import datetime

from lattice.documents.models import (
    DocumentChunk,
    DocumentLink,
    DriftAnalysis,
    DriftStatus,
)
from lattice.providers import get_llm_provider

logger = logging.getLogger(__name__)


DRIFT_ANALYSIS_PROMPT = """You are checking if documentation accurately describes code behavior. Be CONSERVATIVE - only flag real drift.

## Documentation Section
{heading_path}
---
{doc_content}

## Code Being Checked
`{entity_name}` ({entity_type}) in {file_path}
```{language}
{code_content}
```

## CRITICAL: First Check Relevance

Before analyzing drift, determine: Does this documentation section SPECIFICALLY describe this code entity?

- If the doc section is about a DIFFERENT entity/topic → Return "not_relevant"
- If the doc only MENTIONS this entity in passing → Return "not_relevant"
- If the doc SPECIFICALLY documents this entity's behavior → Proceed with drift analysis

## What IS Drift (flag these - MUST have exact quotes):

1. **Behavioral mismatch**: Doc explicitly states a VALUE that differs from code
   - Doc: "tokens expire after 24 hours" → Code: `TOKEN_EXPIRY = 48` ← DIFFERENT VALUE
   - Doc: "retries 5 times" → Code: `max_retries = 3` ← DIFFERENT VALUE
   - You MUST find the specific number/value in both doc AND code that differs

2. **Wrong parameters**: Doc shows different function signature than code has
   - Doc: `login(email, password, remember_me)` → Code: `def login(email, password):`
   - Only flag if the ACTUAL parameter names/count differ

3. **Documented feature completely missing**: Doc claims feature exists but code has NO implementation
   - Doc: "Supports Square payments" → Code: Only StripeProvider and PayPalProvider classes exist
   - The class/function/method must be completely absent, not just undocumented details

## What is NOT Drift (ignore these):

1. **Undocumented code features** - Code has extra methods/params not in docs = OK
2. **Implementation details** - Doc doesn't explain internal algorithm = OK
3. **Private/internal methods** - Methods starting with _ not documented = OK
4. **Order differences** - Steps happen in different order but same result = OK
5. **Additional validation** - Code does more checks than documented = OK
6. **Generic descriptions** - Doc gives high-level overview, code has details = OK

## Response (JSON)

{{
    "relevant": true/false,
    "drift_detected": true/false,
    "drift_severity": "none|minor|major",
    "drift_score": 0.0-1.0,
    "issues": [
        {{
            "type": "behavioral|parameter|missing_feature|wrong_value",
            "doc_quote": "EXACT quote from documentation showing the claim",
            "code_quote": "EXACT code snippet showing different value/behavior",
            "explanation": "Why these differ",
            "severity": "minor|major"
        }}
    ],
    "summary": "One sentence"
}}

CRITICAL: For each issue you MUST provide:
- doc_quote: The EXACT text from the documentation (copy-paste)
- code_quote: The EXACT code that contradicts it (copy-paste)
If you cannot provide exact quotes from BOTH, the issue is not valid drift.

Scoring guide:
- 0.0 = Aligned (no drift or not relevant)
- 0.1-0.3 = Minor (typos, slightly outdated names)
- 0.4-0.6 = Moderate (param differences, minor behavior gaps)
- 0.7-1.0 = Major (documented behavior doesn't match code)

DEFAULT TO ALIGNED unless you find clear evidence of drift with specific quotes."""


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
            heading_display = " > ".join(doc_chunk.heading_path) if doc_chunk.heading_path else "Document"

            prompt = DRIFT_ANALYSIS_PROMPT.format(
                heading_path=heading_display,
                doc_content=doc_chunk.content[:3000],
                entity_name=entity_qualified_name,
                entity_type=entity_type,
                file_path=file_path,
                language=language,
                code_content=code_content[:4000],
            )

            response = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
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
                doc_excerpt=doc_chunk.content[:500],
                code_excerpt=code_content[:500],
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
                "drift_score": 0.5 if drift_detected else 0.0,
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
