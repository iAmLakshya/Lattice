import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lattice.metadata.agent_runner import AgentRunner
from lattice.metadata.models import (
    MetadataGenerationResult,
    MetadataStatus,
    ProjectMetadata,
)
from lattice.metadata.progress import (
    AgentActivity,
    GenerationProgress,
    ProgressTracker,
)
from lattice.shared.config import MetadataConfig

logger = logging.getLogger(__name__)


class MetadataGenerator:
    GENERATION_ORDER = [
        "folder_structure",
        "tech_stack",
        "dependencies",
        "entry_points",
        "core_features",
        "project_overview",
        "architecture_diagram",
    ]

    def __init__(
        self,
        repo_path: str | Path,
        project_name: str,
        max_budget_usd: float = MetadataConfig.default_budget_usd,
        progress_callback: Callable[[GenerationProgress], None] | None = None,
        activity_callback: Callable[[AgentActivity], None] | None = None,
        verbose: bool = True,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.project_name = project_name
        self.max_budget_usd = max_budget_usd
        self._verbose = verbose

        self._tracker = ProgressTracker(
            progress_callback=progress_callback,
            activity_callback=activity_callback,
            verbose=verbose,
        )

        self._runner = AgentRunner(
            repo_path=self.repo_path,
            project_name=project_name,
            progress_tracker=self._tracker,
            verbose=verbose,
        )

    async def generate_all(self) -> ProjectMetadata:
        start_time = time.time()
        results: dict[str, Any] = {}
        total_tokens = 0

        if self._verbose:
            print(f"\nGenerating metadata for: {self.project_name}")
            print(f"Repository: {self.repo_path}\n")

        for field_name in self.GENERATION_ORDER:
            self._tracker.start_field(field_name)
            self._tracker.notify_progress()

            config = MetadataConfig.get_field_config(field_name)
            description = config.get("description", field_name)

            self._tracker.notify_activity(
                AgentActivity(
                    field_name=field_name,
                    activity_type="start",
                    message=description,
                )
            )

            try:
                result = await self._runner.run_field(field_name)
                results[field_name] = result.value
                total_tokens += result.tokens_used
                self._tracker.complete_field(field_name)

                self._tracker.notify_activity(
                    AgentActivity(
                        field_name=field_name,
                        activity_type="complete",
                        message=f"Completed in {result.duration_ms}ms",
                    )
                )

            except Exception as e:
                logger.error(f"Failed to generate {field_name}: {e}", exc_info=True)
                self._tracker.fail_field(field_name)
                results[field_name] = None

                self._tracker.notify_activity(
                    AgentActivity(
                        field_name=field_name,
                        activity_type="error",
                        message=f"Failed: {e}",
                    )
                )

            self._tracker.notify_progress()

        status = self._determine_status()
        elapsed_ms = int((time.time() - start_time) * 1000)

        self._tracker.set_elapsed(elapsed_ms)
        self._tracker.set_tokens(total_tokens)

        if self._verbose:
            progress = self._tracker.progress
            completed = len(progress.completed_fields)
            total = len(self.GENERATION_ORDER)
            print(f"\nCompleted {completed}/{total} fields in {elapsed_ms / 1000:.1f}s")

        return self._build_metadata(results, elapsed_ms, total_tokens, status)

    async def generate_field(self, field_name: str) -> MetadataGenerationResult:
        if field_name not in self.GENERATION_ORDER:
            raise ValueError(f"Unknown field: {field_name}")

        return await self._runner.run_field(field_name)

    def _determine_status(self) -> MetadataStatus:
        progress = self._tracker.progress
        if len(progress.failed_fields) == 0:
            return MetadataStatus.COMPLETED
        elif len(progress.completed_fields) > 0:
            return MetadataStatus.PARTIAL
        else:
            return MetadataStatus.FAILED

    def _build_metadata(
        self,
        results: dict[str, Any],
        elapsed_ms: int,
        total_tokens: int,
        status: MetadataStatus,
    ) -> ProjectMetadata:
        return ProjectMetadata(
            project_name=self.project_name,
            folder_structure=results.get("folder_structure"),
            project_overview=results.get("project_overview"),
            core_features=results.get("core_features") or [],
            architecture_diagram=results.get("architecture_diagram"),
            tech_stack=results.get("tech_stack"),
            dependencies=results.get("dependencies"),
            entry_points=results.get("entry_points") or [],
            generation_model="claude-code-sdk",
            generation_duration_ms=elapsed_ms,
            generation_tokens_used=total_tokens,
            status=status,
        )
