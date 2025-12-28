"""Tests for DriftDetector and LineRangeCalibrator."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from lattice.documents.drift_detector import DriftDetector, LineRangeCalibrator
from lattice.documents.models import DocumentChunk, DocumentLink, DriftStatus, LinkType


class TestDriftDetector:
    @pytest.fixture
    def mock_llm_provider(self):
        mock = AsyncMock()
        mock.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "drift_detected": True,
                    "drift_severity": "minor",
                    "drift_score": 0.3,
                    "issues": [
                        {
                            "type": "parameter",
                            "description": "Timeout value differs",
                            "doc_says": "10 seconds",
                            "code_does": "30 seconds",
                            "severity": "minor",
                        }
                    ],
                    "summary": "Minor drift in timeout configuration.",
                }
            )
        )
        return mock

    @pytest.fixture
    def detector(self, mock_llm_provider):
        with patch(
            "lattice.documents.drift_detector.get_llm_provider",
            return_value=mock_llm_provider,
        ):
            return DriftDetector()

    @pytest.fixture
    def sample_chunk(self):
        return DocumentChunk(
            id=uuid4(),
            document_id=uuid4(),
            project_name="test-project",
            content="## Configuration\n\nSet timeout to 10 seconds for API calls.",
            heading_path=["API", "Configuration"],
            heading_level=2,
            start_line=15,
            end_line=20,
            content_hash="dochash123",
        )

    @pytest.mark.asyncio
    async def test_analyze_detects_drift(self, detector, sample_chunk, mock_llm_provider):
        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="api.client.make_request",
            entity_type="Function",
            file_path="/src/api/client.py",
            code_content="def make_request():\n    timeout = 30\n    ...",
            code_hash="codehash456",
        )

        assert analysis.drift_detected is True
        assert analysis.drift_severity == DriftStatus.MINOR_DRIFT
        assert analysis.drift_score == 0.3
        assert len(analysis.issues) == 1
        assert analysis.issues[0]["type"] == "parameter"
        assert analysis.doc_version_hash == "dochash123"
        assert analysis.code_version_hash == "codehash456"

    @pytest.mark.asyncio
    async def test_analyze_no_drift(self, detector, sample_chunk, mock_llm_provider):
        mock_llm_provider.complete.return_value = json.dumps(
            {
                "drift_detected": False,
                "drift_severity": "none",
                "drift_score": 0.0,
                "issues": [],
                "summary": "Documentation matches code implementation.",
            }
        )

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="api.client.make_request",
            entity_type="Function",
            file_path="/src/api/client.py",
            code_content="def make_request():\n    timeout = 10\n    ...",
            code_hash="codehash789",
        )

        assert analysis.drift_detected is False
        assert analysis.drift_severity == DriftStatus.ALIGNED
        assert analysis.drift_score == 0.0
        assert len(analysis.issues) == 0

    @pytest.mark.asyncio
    async def test_analyze_major_drift(self, detector, sample_chunk, mock_llm_provider):
        mock_llm_provider.complete.return_value = json.dumps(
            {
                "drift_detected": True,
                "drift_severity": "major",
                "drift_score": 0.8,
                "issues": [
                    {
                        "type": "behavioral",
                        "description": "Function completely different behavior",
                        "doc_says": "Sends email notification",
                        "code_does": "Only logs to console",
                        "severity": "major",
                    }
                ],
                "summary": "Major behavioral drift detected.",
            }
        )

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="notifications.send",
            entity_type="Function",
            file_path="/src/notifications.py",
            code_content="def send():\n    print('notification')",
            code_hash="code123",
        )

        assert analysis.drift_detected is True
        assert analysis.drift_severity == DriftStatus.MAJOR_DRIFT
        assert analysis.drift_score == 0.8

    @pytest.mark.asyncio
    async def test_analyze_handles_json_with_code_block(
        self, detector, sample_chunk, mock_llm_provider
    ):
        mock_llm_provider.complete.return_value = """```json
{
    "drift_detected": true,
    "drift_severity": "minor",
    "drift_score": 0.2,
    "issues": [],
    "summary": "Minor drift."
}
```"""

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="test.func",
            entity_type="Function",
            file_path="/src/test.py",
            code_content="def func(): pass",
            code_hash="hash",
        )

        assert analysis.drift_detected is True
        assert analysis.drift_severity == DriftStatus.MINOR_DRIFT

    @pytest.mark.asyncio
    async def test_analyze_handles_invalid_json(
        self, detector, sample_chunk, mock_llm_provider
    ):
        mock_llm_provider.complete.return_value = "This is not valid JSON response"

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="test.func",
            entity_type="Function",
            file_path="/src/test.py",
            code_content="def func(): pass",
            code_hash="hash",
        )

        assert analysis.drift_severity == DriftStatus.ALIGNED

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_error(
        self, detector, sample_chunk, mock_llm_provider
    ):
        mock_llm_provider.complete.side_effect = Exception("API Error")

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="test.func",
            entity_type="Function",
            file_path="/src/test.py",
            code_content="def func(): pass",
            code_hash="hash",
        )

        assert analysis is None

    @pytest.mark.asyncio
    async def test_analyze_records_excerpts(
        self, detector, sample_chunk, mock_llm_provider
    ):
        code_content = "def my_function():\n    return 'hello'\n"

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="test.my_function",
            entity_type="Function",
            file_path="/src/test.py",
            code_content=code_content,
            code_hash="hash",
        )

        assert len(analysis.doc_excerpt) > 0
        assert len(analysis.code_excerpt) > 0

    @pytest.mark.asyncio
    async def test_analyze_records_analyzed_at(
        self, detector, sample_chunk, mock_llm_provider
    ):
        before = datetime.now()

        analysis = await detector.analyze(
            doc_chunk=sample_chunk,
            doc_path="/docs/api.md",
            entity_qualified_name="test.func",
            entity_type="Function",
            file_path="/src/test.py",
            code_content="def func(): pass",
            code_hash="hash",
        )

        after = datetime.now()

        assert analysis.analyzed_at >= before
        assert analysis.analyzed_at <= after

    def test_parse_response_valid_json(self, detector):
        response = json.dumps(
            {
                "drift_detected": True,
                "drift_severity": "minor",
                "drift_score": 0.4,
                "issues": [],
                "summary": "Test",
            }
        )

        result = detector._parse_response(response)

        assert result["drift_detected"] is True
        assert result["drift_severity"] == "minor"

    def test_parse_response_with_markdown_fence(self, detector):
        response = """```json
{
    "drift_detected": false,
    "drift_severity": "none",
    "drift_score": 0.0,
    "issues": [],
    "summary": "No drift"
}
```"""

        result = detector._parse_response(response)

        assert result["drift_detected"] is False

    def test_parse_response_with_generic_fence(self, detector):
        response = """```
{
    "drift_detected": true,
    "drift_severity": "major",
    "drift_score": 0.9,
    "issues": [],
    "summary": "Major drift"
}
```"""

        result = detector._parse_response(response)

        assert result["drift_detected"] is True
        assert result["drift_severity"] == "major"

    def test_parse_response_invalid_json_with_drift_mention(self, detector):
        response = "The drift_detected is true because..."

        result = detector._parse_response(response)

        assert result["drift_detected"] is True
        assert result["drift_severity"] == "unknown"

    def test_parse_response_invalid_json_without_drift(self, detector):
        response = "Everything looks good."

        result = detector._parse_response(response)

        assert result["drift_detected"] is False


class TestLineRangeCalibrator:
    @pytest.fixture
    def calibrator(self):
        return LineRangeCalibrator()

    @pytest.fixture
    def sample_link(self):
        return DocumentLink(
            id=uuid4(),
            document_chunk_id=uuid4(),
            code_entity_qualified_name="test.MyClass.method",
            code_entity_type="Method",
            code_file_path="/src/test.py",
            link_type=LinkType.EXPLICIT,
            confidence_score=0.9,
            line_range_start=10,
            line_range_end=20,
            code_version_hash="oldhash",
        )

    @pytest.mark.asyncio
    async def test_calibrate_same_size(self, calibrator, sample_link):
        new_start, new_end, needs_review = await calibrator.calibrate(
            link=sample_link,
            new_start_line=15,
            new_end_line=25,
            new_code_hash="newhash",
        )

        assert new_start == 15
        assert new_end == 25
        assert needs_review is False

    @pytest.mark.asyncio
    async def test_calibrate_size_changed(self, calibrator, sample_link):
        new_start, new_end, needs_review = await calibrator.calibrate(
            link=sample_link,
            new_start_line=10,
            new_end_line=30,
            new_code_hash="newhash",
        )

        assert new_start == 10
        assert new_end == 30
        assert needs_review is True

    @pytest.mark.asyncio
    async def test_calibrate_no_previous_range(self, calibrator):
        link = DocumentLink(
            id=uuid4(),
            document_chunk_id=uuid4(),
            code_entity_qualified_name="test.func",
            code_entity_type="Function",
            code_file_path="/src/test.py",
            link_type=LinkType.IMPLICIT,
            confidence_score=0.7,
            line_range_start=None,
            line_range_end=None,
            code_version_hash=None,
        )

        new_start, new_end, needs_review = await calibrator.calibrate(
            link=link,
            new_start_line=5,
            new_end_line=15,
            new_code_hash="hash",
        )

        assert new_start == 5
        assert new_end == 15
        assert needs_review is False

    @pytest.mark.asyncio
    async def test_calibrate_smaller_size(self, calibrator, sample_link):
        new_start, new_end, needs_review = await calibrator.calibrate(
            link=sample_link,
            new_start_line=10,
            new_end_line=15,
            new_code_hash="newhash",
        )

        assert needs_review is True

    @pytest.mark.asyncio
    async def test_calibrate_larger_size(self, calibrator, sample_link):
        new_start, new_end, needs_review = await calibrator.calibrate(
            link=sample_link,
            new_start_line=10,
            new_end_line=35,
            new_code_hash="newhash",
        )

        assert needs_review is True
