"""Tests for the indexing pipeline."""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from lattice.indexing.orchestrator import PipelineOrchestrator
from lattice.indexing.progress import ProgressTracker
from lattice.shared.types import PipelineStage
from lattice.parsing.scanner import FileScanner
from lattice.parsing.parser import create_code_parser


def create_mock_orchestrator(
    repo_path: Path,
    progress_callback=None,
    force: bool = False,
    skip_metadata: bool = False,
) -> PipelineOrchestrator:
    return PipelineOrchestrator(
        repo_path=repo_path,
        project_name=repo_path.name,
        progress_callback=progress_callback,
        force=force,
        skip_metadata=skip_metadata,
        memgraph_client=MagicMock(),
        qdrant_client=MagicMock(),
        parser=create_code_parser(),
        embedder=MagicMock(),
        summarizer=MagicMock(),
        max_workers=4,
        max_concurrent_api=5,
    )


class TestProgressTracker:
    """Tests for ProgressTracker."""

    def test_initial_state(self):
        """Test tracker starts in scanning state."""
        tracker = ProgressTracker()
        assert tracker.progress.current_stage == PipelineStage.SCANNING
        assert not tracker.progress.is_running
        assert not tracker.progress.is_complete

    def test_start(self):
        """Test starting the tracker."""
        tracker = ProgressTracker()
        tracker.start()
        assert tracker.progress.is_running
        assert tracker.progress.start_time is not None

    def test_set_stage(self):
        """Test setting stages."""
        tracker = ProgressTracker()
        tracker.start()
        tracker.set_stage(PipelineStage.PARSING, total=10, message="Parsing...")

        assert tracker.progress.current_stage == PipelineStage.PARSING
        assert PipelineStage.PARSING in tracker.progress.stages
        assert tracker.progress.stages[PipelineStage.PARSING].total == 10

    def test_update_stage(self):
        """Test updating stage progress."""
        tracker = ProgressTracker()
        tracker.start()
        tracker.set_stage(PipelineStage.PARSING, total=10)
        tracker.update_stage(5)

        assert tracker.progress.stages[PipelineStage.PARSING].current == 5
        assert tracker.progress.stages[PipelineStage.PARSING].percentage == 50.0

    def test_complete(self):
        """Test completing the pipeline."""
        tracker = ProgressTracker()
        tracker.start()
        tracker.complete()

        assert tracker.progress.current_stage == PipelineStage.COMPLETED
        assert tracker.progress.is_complete
        assert not tracker.progress.is_running
        assert tracker.progress.end_time is not None

    def test_error(self):
        """Test error state."""
        tracker = ProgressTracker()
        tracker.start()
        tracker.error("Something went wrong")

        assert tracker.progress.current_stage == PipelineStage.FAILED
        assert tracker.progress.has_error
        assert tracker.progress.error_message == "Something went wrong"

    def test_callbacks(self):
        """Test progress callbacks."""
        tracker = ProgressTracker()
        callback_calls = []

        def callback(progress):
            callback_calls.append(progress.current_stage)

        tracker.add_callback(callback)
        tracker.start()
        tracker.set_stage(PipelineStage.PARSING)
        tracker.complete()

        assert len(callback_calls) >= 3
        assert PipelineStage.COMPLETED in callback_calls


class TestPipelineScanAndParse:
    """Tests for scanning and parsing stages (no external dependencies)."""

    @pytest.mark.asyncio
    async def test_scan_files(self, sample_project_path: Path):
        """Test file scanning stage."""
        # Create orchestrator but don't run full pipeline
        orchestrator = create_mock_orchestrator(sample_project_path)

        # Test scanning directly
        scanner = FileScanner(sample_project_path)
        files = scanner.scan_all()

        assert len(files) > 0
        assert orchestrator.repo_path == sample_project_path

    @pytest.mark.asyncio
    async def test_parse_files(self, sample_project_path: Path):
        """Test file parsing stage."""
        scanner = FileScanner(sample_project_path)
        parser = create_code_parser()

        files = scanner.scan_all()
        parsed_files = []
        errors = []

        for file_info in files:
            try:
                parsed = parser.parse_file(file_info)
                parsed_files.append(parsed)
            except Exception as e:
                errors.append((file_info.relative_path, str(e)))

        assert len(parsed_files) > 0, "Should parse some files"
        assert len(errors) == 0, f"Should have no parsing errors: {errors}"

        # Check we found entities
        total_entities = sum(len(pf.all_entities) for pf in parsed_files)
        assert total_entities > 0, "Should find entities"


class TestPipelineWithMocks:
    """Tests for pipeline with mocked external services."""

    @pytest.mark.asyncio
    async def test_pipeline_stages_execute(self, sample_project_path: Path):
        """Test that all pipeline stages execute."""
        # Track which stages were reached
        stages_reached = []

        def progress_callback(progress):
            if progress.current_stage not in stages_reached:
                stages_reached.append(progress.current_stage)

        # Create orchestrator
        orchestrator = create_mock_orchestrator(
            sample_project_path,
            progress_callback=progress_callback,
        )

        # Mock cleanup
        orchestrator._cleanup = AsyncMock()

        # Mock all stages
        for stage in orchestrator._stages:
            stage.execute = AsyncMock()

        try:
            result = await orchestrator.run()
        except Exception as e:
            pytest.fail(f"Pipeline failed: {e}")

        # Check stages were reached (with mocked stages, only COMPLETED is tracked)
        assert PipelineStage.COMPLETED in stages_reached

        # Verify all stages were executed
        for stage in orchestrator._stages:
            if stage.name != "metadata" or not orchestrator.skip_metadata:
                stage.execute.assert_called_once()


@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="RUN_INTEGRATION_TESTS not set (these tests make real API calls)"
)
class TestPipelineIntegration:
    """Full integration tests (requires API keys and running databases).

    Run with: RUN_INTEGRATION_TESTS=1 pytest tests/test_pipeline.py
    """

    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_project_path: Path):
        """Test the full indexing pipeline."""
        from lattice.indexing.api import create_pipeline_orchestrator

        progress_updates = []

        def progress_callback(progress):
            progress_updates.append({
                "stage": progress.current_stage.value,
                "files": progress.files_parsed,
                "entities": progress.entities_found,
            })

        orchestrator = await create_pipeline_orchestrator(
            repo_path=sample_project_path,
            project_name="test_project",
            progress_callback=progress_callback,
        )

        result = await orchestrator.run()

        # Verify results
        assert result["files_indexed"] > 0
        assert result["entities_found"] > 0
        assert result["elapsed_seconds"] > 0

        # Verify progress was tracked
        assert len(progress_updates) > 0

        print(f"\nIndexing results:")
        print(f"  Files: {result['files_indexed']}")
        print(f"  Entities: {result['entities_found']}")
        print(f"  Graph nodes: {result['graph_nodes']}")
        print(f"  Summaries: {result['summaries']}")
        print(f"  Chunks: {result['chunks_embedded']}")
        print(f"  Time: {result['elapsed_seconds']:.2f}s")


class TestPipelineEdgeCases:
    """Tests for edge cases in the pipeline."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, tmp_path: Path):
        """Test pipeline with empty directory."""
        orchestrator = create_mock_orchestrator(tmp_path)
        orchestrator._cleanup = AsyncMock()

        for stage in orchestrator._stages:
            stage.execute = AsyncMock()

        result = await orchestrator.run()

        assert result["files_indexed"] == 0
        assert result["entities_found"] == 0

    @pytest.mark.asyncio
    async def test_directory_with_no_supported_files(self, tmp_path: Path):
        """Test pipeline with unsupported file types."""
        # Create files with unsupported extensions
        (tmp_path / "readme.md").write_text("# README")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "config.yaml").write_text("key: value")

        orchestrator = create_mock_orchestrator(tmp_path)
        orchestrator._cleanup = AsyncMock()

        for stage in orchestrator._stages:
            stage.execute = AsyncMock()

        result = await orchestrator.run()

        assert result["files_indexed"] == 0

    def test_nonexistent_directory(self):
        """Test pipeline with non-existent directory."""
        with pytest.raises(ValueError, match="Path does not exist"):
            scanner = FileScanner("/nonexistent/path")
