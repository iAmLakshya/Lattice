import asyncio
import json
import logging
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lattice.core.errors import MetadataError
from lattice.metadata.models import (
    CoreFeature,
    DependencyInfo,
    EntryPoint,
    FolderNode,
    MetadataGenerationResult,
    MetadataStatus,
    ProjectMetadata,
    TechStack,
)
from lattice.metadata.prompts import MetadataPrompts

logger = logging.getLogger(__name__)


FIELD_CONFIG = {
    "folder_structure": {
        "model": "claude-haiku-4-5-20251001",
        "max_budget_usd": 0.50,
        "description": "Exploring folder structure",
    },
    "tech_stack": {
        "model": "claude-haiku-4-5-20251001",
        "max_budget_usd": 0.30,
        "description": "Identifying technology stack",
    },
    "dependencies": {
        "model": "claude-haiku-4-5-20251001",
        "max_budget_usd": 0.20,
        "description": "Analyzing dependencies",
    },
    "entry_points": {
        "model": "claude-sonnet-4-5-20250929",
        "max_budget_usd": 0.50,
        "description": "Finding entry points",
    },
    "core_features": {
        "model": "claude-sonnet-4-5-20250929",
        "max_budget_usd": 1.00,
        "description": "Identifying core features",
    },
    "project_overview": {
        "model": "claude-sonnet-4-5-20250929",
        "max_budget_usd": 0.50,
        "description": "Writing project overview",
    },
    "architecture_diagram": {
        "model": "claude-sonnet-4-5-20250929",
        "max_budget_usd": 0.50,
        "description": "Creating architecture diagram",
    },
}


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
        max_budget_usd: float = 0.50,
        progress_callback: Callable[[GenerationProgress], None] | None = None,
        activity_callback: Callable[[AgentActivity], None] | None = None,
        verbose: bool = True,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.project_name = project_name
        self.max_budget_usd = max_budget_usd
        self._progress_callback = progress_callback
        self._activity_callback = activity_callback
        self._verbose = verbose

        self._prompts = MetadataPrompts(self.repo_path, project_name)
        self._progress = GenerationProgress()

    def _notify_progress(self) -> None:
        if self._progress_callback:
            self._progress_callback(self._progress)

    def _notify_activity(self, activity: AgentActivity) -> None:
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
            config = FIELD_CONFIG.get(activity.field_name, {})
            model = config.get("model", "default").split("-")[1]
            print(f"\n{prefix} {activity.message} (using {model})", flush=True)

        elif activity.activity_type == "complete":
            print(f"  {prefix} {activity.message}", flush=True)

        elif activity.activity_type == "error":
            print(f"  {prefix} {activity.message}", file=sys.stderr, flush=True)

    async def generate_all(self) -> ProjectMetadata:
        start_time = time.time()
        results: dict[str, Any] = {}
        total_tokens = 0

        if self._verbose:
            print(f"\nGenerating metadata for: {self.project_name}")
            print(f"Repository: {self.repo_path}\n")

        for field_name in self.GENERATION_ORDER:
            self._progress.current_field = field_name
            self._notify_progress()

            config = FIELD_CONFIG.get(field_name, {})
            description = config.get("description", field_name)

            self._notify_activity(
                AgentActivity(
                    field_name=field_name,
                    activity_type="start",
                    message=description,
                )
            )

            try:
                result = await self._generate_field(field_name)
                results[field_name] = result.value
                total_tokens += result.tokens_used
                self._progress.completed_fields.append(field_name)

                self._notify_activity(
                    AgentActivity(
                        field_name=field_name,
                        activity_type="complete",
                        message=f"Completed in {result.duration_ms}ms",
                    )
                )

            except Exception as e:
                logger.error(f"Failed to generate {field_name}: {e}", exc_info=True)
                self._progress.failed_fields.append(field_name)
                results[field_name] = None

                self._notify_activity(
                    AgentActivity(
                        field_name=field_name,
                        activity_type="error",
                        message=f"Failed: {e}",
                    )
                )

            self._notify_progress()

        if len(self._progress.failed_fields) == 0:
            status = MetadataStatus.COMPLETED
        elif len(self._progress.completed_fields) > 0:
            status = MetadataStatus.PARTIAL
        else:
            status = MetadataStatus.FAILED

        elapsed_ms = int((time.time() - start_time) * 1000)
        self._progress.elapsed_ms = elapsed_ms
        self._progress.tokens_used = total_tokens

        if self._verbose:
            completed = len(self._progress.completed_fields)
            total = len(self.GENERATION_ORDER)
            print(f"\nCompleted {completed}/{total} fields in {elapsed_ms / 1000:.1f}s")

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

    async def generate_field(self, field_name: str) -> MetadataGenerationResult:
        if field_name not in self.GENERATION_ORDER:
            raise ValueError(f"Unknown field: {field_name}")

        return await self._generate_field(field_name)

    async def _generate_field(
        self, field_name: str, max_retries: int = 2
    ) -> MetadataGenerationResult:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
        )

        config = FIELD_CONFIG.get(field_name, {})
        model = config.get("model", "claude-sonnet-4-5-20250929")
        max_budget = config.get("max_budget_usd", 0.10)
        last_error = None

        for attempt in range(max_retries):
            start_time = time.time()
            prompt = self._prompts.get_prompt(field_name)

            if field_name not in ("project_overview", "architecture_diagram"):
                prompt += (
                    "\n\nCRITICAL: After gathering key information, output the JSON "
                    "in a ```json code block. Do not explore indefinitely - be efficient, "
                    "gather what you need, then output results. Quality over completeness."
                )

            if attempt > 0 and self._verbose:
                print(f"  [retry] {attempt + 1}/{max_retries}", flush=True)

            options = ClaudeAgentOptions(
                allowed_tools=["Read", "Glob", "Grep", "Bash"],
                permission_mode="acceptEdits",
                cwd=str(self.repo_path),
                max_budget_usd=max_budget,
                model=model,
            )

            accumulated_content = ""
            tool_calls = 0

            try:
                async with ClaudeSDKClient(options=options) as client:
                    await client.query(prompt)

                    async for message in client.receive_messages():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, TextBlock):
                                    accumulated_content += block.text + "\n"
                                elif isinstance(block, ToolUseBlock):
                                    tool_calls += 1
                                    self._notify_activity(
                                        AgentActivity(
                                            field_name=field_name,
                                            activity_type="tool_call",
                                            message=f"Using {block.name}",
                                            tool_name=block.name,
                                            tool_input=block.input
                                            if hasattr(block, "input")
                                            else None,
                                        )
                                    )
                                elif isinstance(block, ToolResultBlock):
                                    pass

                        elif isinstance(message, ResultMessage):
                            subtype = getattr(message, "subtype", "unknown")
                            is_error = getattr(message, "is_error", False)

                            if hasattr(message, "result") and message.result:
                                accumulated_content += str(message.result)

                            if is_error or subtype != "success":
                                if self._verbose:
                                    print(f"  [warn] {subtype}", flush=True)
                            break

            except Exception as e:
                last_error = e
                logger.warning(f"Agent query failed for {field_name}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise MetadataError(
                    f"Agent query failed for {field_name}: {e}",
                    field_name=field_name,
                    cause=e,
                )

            elapsed_ms = int((time.time() - start_time) * 1000)
            all_content = accumulated_content.strip()

            if not all_content:
                logger.warning(f"{field_name}: No content ({tool_calls} tools)")
                last_error = ValueError("No content received from agent")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise MetadataError(
                    f"No content received for {field_name}",
                    field_name=field_name,
                )

            try:
                parsed_value = self._parse_field_response(field_name, all_content)
                return MetadataGenerationResult(
                    field_name=field_name,
                    status=MetadataStatus.COMPLETED,
                    value=parsed_value,
                    duration_ms=elapsed_ms,
                    tokens_used=0,
                )
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to parse {field_name}: {e}")
                if self._verbose and attempt == max_retries - 1:
                    print(f"\n  [Debug] Response ({len(all_content)} chars):")
                    print(f"  {all_content[:500]}...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue

        raise MetadataError(
            f"Failed to generate {field_name} after {max_retries} attempts: {last_error}",
            field_name=field_name,
            cause=last_error,
        )

    def _parse_field_response(self, field_name: str, content: str) -> Any:
        if field_name in ("project_overview", "architecture_diagram"):
            json_str = self._extract_json(content)
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        return (
                            parsed.get("overview")
                            or parsed.get("diagram")
                            or parsed.get("content")
                            or str(parsed)
                        )
                except json.JSONDecodeError:
                    pass
            content = self._strip_code_blocks(content)
            return content.strip()

        json_str = self._extract_json(content)
        if not json_str:
            raise ValueError(f"No JSON found in response for {field_name}")

        parsed = json.loads(json_str)

        if field_name == "folder_structure":
            return FolderNode.model_validate(parsed)
        elif field_name == "tech_stack":
            return TechStack.model_validate(parsed)
        elif field_name == "dependencies":
            return DependencyInfo.model_validate(parsed)
        elif field_name == "entry_points":
            if not isinstance(parsed, list):
                parsed = [parsed]
            return [EntryPoint.model_validate(e) for e in parsed]
        elif field_name == "core_features":
            if not isinstance(parsed, list):
                parsed = [parsed]
            return [CoreFeature.model_validate(f) for f in parsed]
        else:
            return parsed

    def _extract_json(self, content: str) -> str | None:
        code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
        for match in re.finditer(code_block_pattern, content):
            candidate = match.group(1).strip()
            if candidate:
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue

        result = self._find_json_by_brackets(content)
        if result:
            return result

        return None

    def _find_json_by_brackets(self, content: str) -> str | None:
        first_obj = content.find("{")
        first_arr = content.find("[")

        if first_obj == -1 and first_arr == -1:
            return None
        elif first_arr == -1:
            order = [("{", "}")]
        elif first_obj == -1:
            order = [("[", "]")]
        elif first_arr < first_obj:
            order = [("[", "]"), ("{", "}")]
        else:
            order = [("{", "}"), ("[", "]")]

        for start_char, end_char in order:
            start_idx = content.find(start_char)
            if start_idx != -1:
                depth = 0
                in_string = False
                escape_next = False

                for i, char in enumerate(content[start_idx:], start_idx):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == "\\":
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            candidate = content[start_idx : i + 1]
                            try:
                                json.loads(candidate)
                                return candidate
                            except json.JSONDecodeError:
                                break
        return None

    def _strip_code_blocks(self, content: str) -> str:
        content = re.sub(r"```\w*\n?", "", content)
        return content.strip()
