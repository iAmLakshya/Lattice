import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from lattice.metadata.models import MetadataGenerationResult, MetadataStatus
from lattice.metadata.parsers import parse_field_response
from lattice.metadata.progress import AgentActivity, ProgressTracker
from lattice.prompts.loader import get_prompt
from lattice.shared.config import MetadataConfig
from lattice.shared.exceptions import MetadataError

logger = logging.getLogger(__name__)


class AgentRunner:
    def __init__(
        self,
        repo_path: Path,
        project_name: str,
        progress_tracker: ProgressTracker,
        verbose: bool = True,
    ):
        self._repo_path = repo_path
        self._project_name = project_name
        self._tracker = progress_tracker
        self._verbose = verbose

    async def run_field(
        self, field_name: str, max_retries: int = MetadataConfig.max_retries
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

        config = MetadataConfig.get_field_config(field_name)
        model = config.get("model", "claude-sonnet-4-5-20250929")
        max_budget = config.get("max_budget_usd", 0.10)
        last_error: Exception | None = None

        for attempt in range(max_retries):
            start_time = time.time()
            prompt = self._build_prompt(field_name)

            if attempt > 0 and self._verbose:
                print(f"  [retry] {attempt + 1}/{max_retries}", flush=True)

            options = ClaudeAgentOptions(
                allowed_tools=["Read", "Glob", "Grep", "Bash"],
                permission_mode="acceptEdits",
                cwd=str(self._repo_path),
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
                            accumulated_content, tool_calls = self._process_assistant(
                                message,
                                field_name,
                                accumulated_content,
                                tool_calls,
                                TextBlock,
                                ToolUseBlock,
                                ToolResultBlock,
                            )

                        elif isinstance(message, ResultMessage):
                            accumulated_content = self._process_result(message, accumulated_content)
                            break

            except Exception as e:
                last_error = e
                logger.warning(f"Agent query failed for {field_name}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(MetadataConfig.default_retry_delay)
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
                    await asyncio.sleep(MetadataConfig.default_retry_delay)
                    continue
                raise MetadataError(
                    f"No content received for {field_name}",
                    field_name=field_name,
                )

            try:
                parsed_value = parse_field_response(field_name, all_content)
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
                    await asyncio.sleep(MetadataConfig.default_retry_delay)
                    continue

        raise MetadataError(
            f"Failed to generate {field_name} after {max_retries} attempts: {last_error}",
            field_name=field_name,
            cause=last_error,
        )

    def _build_prompt(self, field_name: str) -> str:
        ignore_patterns_str = ", ".join(MetadataConfig.get_ignore_patterns())
        prompt = get_prompt(
            "metadata",
            field_name,
            repo_path=str(self._repo_path),
            project_name=self._project_name,
            ignore_patterns=ignore_patterns_str,
        )

        if field_name not in ("project_overview", "architecture_diagram"):
            json_suffix = get_prompt("metadata", "json_output_suffix")
            prompt += f"\n\n{json_suffix}"

        return prompt

    def _process_assistant(
        self,
        message: Any,
        field_name: str,
        accumulated_content: str,
        tool_calls: int,
        text_block_cls: type,
        tool_use_block_cls: type,
        tool_result_block_cls: type,
    ) -> tuple[str, int]:
        for block in message.content:
            if isinstance(block, text_block_cls):
                accumulated_content += block.text + "\n"
            elif isinstance(block, tool_use_block_cls):
                tool_calls += 1
                self._tracker.notify_activity(
                    AgentActivity(
                        field_name=field_name,
                        activity_type="tool_call",
                        message=f"Using {block.name}",
                        tool_name=block.name,
                        tool_input=block.input if hasattr(block, "input") else None,
                    )
                )
            elif isinstance(block, tool_result_block_cls):
                pass
        return accumulated_content, tool_calls

    def _process_result(self, message: Any, accumulated_content: str) -> str:
        subtype = getattr(message, "subtype", "unknown")
        is_error = getattr(message, "is_error", False)

        if hasattr(message, "result") and message.result:
            accumulated_content += str(message.result)

        if is_error or subtype != "success":
            if self._verbose:
                print(f"  [warn] {subtype}", flush=True)

        return accumulated_content
