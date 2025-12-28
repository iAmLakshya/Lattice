import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from lattice.shared.config import MetadataConfig


@dataclass
class AgentActivity:
    field_name: str
    activity_type: str
    message: str
    tool_name: str | None = None
    tool_input: dict | None = None


@dataclass
class GenerationProgress:
    current_field: str = ""
    completed_fields: list[str] = field(default_factory=list)
    failed_fields: list[str] = field(default_factory=list)
    total_fields: int = 7
    tokens_used: int = 0
    elapsed_ms: int = 0

    @property
    def progress_percentage(self) -> float:
        completed = len(self.completed_fields) + len(self.failed_fields)
        return (completed / self.total_fields) * 100 if self.total_fields > 0 else 0


class ProgressTracker:
    def __init__(
        self,
        progress_callback: Callable[[GenerationProgress], None] | None = None,
        activity_callback: Callable[[AgentActivity], None] | None = None,
        verbose: bool = True,
    ):
        self._progress_callback = progress_callback
        self._activity_callback = activity_callback
        self._verbose = verbose
        self._progress = GenerationProgress()

    @property
    def progress(self) -> GenerationProgress:
        return self._progress

    def notify_progress(self) -> None:
        if self._progress_callback:
            self._progress_callback(self._progress)

    def notify_activity(self, activity: AgentActivity) -> None:
        if self._activity_callback:
            self._activity_callback(activity)
        if self._verbose:
            self._print_activity(activity)

    def _print_activity(self, activity: AgentActivity) -> None:
        prefixes = {
            "tool_call": "[tool]",
            "thinking": "[...]",
            "response": "[out]",
            "complete": "[done]",
            "error": "[err]",
            "start": "[>]",
        }
        prefix = prefixes.get(activity.activity_type, "-")

        if activity.activity_type == "tool_call" and activity.tool_name:
            tool_detail = ""
            if activity.tool_input:
                if activity.tool_name == "Read":
                    tool_detail = activity.tool_input.get("file_path", "")
                    if tool_detail:
                        tool_detail = f" {Path(tool_detail).name}"
                elif activity.tool_name == "Glob":
                    tool_detail = f" {activity.tool_input.get('pattern', '')}"
                elif activity.tool_name == "Grep":
                    tool_detail = f" '{activity.tool_input.get('pattern', '')}'"
                elif activity.tool_name == "Bash":
                    cmd = activity.tool_input.get("command", "")
                    tool_detail = f" {cmd[:40]}..." if len(cmd) > 40 else f" {cmd}"

            print(f"  {prefix} {activity.tool_name}{tool_detail}", flush=True)

        elif activity.activity_type == "start":
            config = MetadataConfig.get_field_config(activity.field_name)
            model = config.get("model", "default").split("-")[1]
            print(f"\n{prefix} {activity.message} (using {model})", flush=True)

        elif activity.activity_type == "complete":
            print(f"  {prefix} {activity.message}", flush=True)

        elif activity.activity_type == "error":
            print(f"  {prefix} {activity.message}", file=sys.stderr, flush=True)

    def start_field(self, field_name: str) -> None:
        self._progress.current_field = field_name

    def complete_field(self, field_name: str) -> None:
        self._progress.completed_fields.append(field_name)

    def fail_field(self, field_name: str) -> None:
        self._progress.failed_fields.append(field_name)

    def set_elapsed(self, elapsed_ms: int) -> None:
        self._progress.elapsed_ms = elapsed_ms

    def set_tokens(self, tokens: int) -> None:
        self._progress.tokens_used = tokens
