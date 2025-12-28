"""Code retrieval tool for MCP."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lattice.mcp.tools.models import CodeSnippet

logger = logging.getLogger(__name__)


def create_code_retrieval_tool(
    project_root: Path,
    graph_client_factory: Callable[..., Any],
) -> dict[str, Any]:
    """Create the get_code_snippet tool.

    Args:
        project_root: Root path of the indexed project.
        graph_client_factory: Factory function to create MemgraphClient.

    Returns:
        Tool definition dict for MCP registration.
    """

    async def get_code_snippet(
        qualified_name: str,
    ) -> CodeSnippet:
        """Retrieve source code for a specific function, class, or method.

        Use the fully qualified name to retrieve the actual source code
        from the codebase. This is useful after finding entities through
        search or query tools.

        Args:
            qualified_name: Full qualified name (e.g., "myproject.models.User.save").

        Returns:
            CodeSnippet with source code and location info.

        Examples:
            - "myproject.models.User"
            - "myproject.api.endpoints.create_user"
            - "myproject.utils.helpers.format_date"
        """
        logger.info(f"[Tool:GetCode] Retrieving: {qualified_name}")

        try:
            client = graph_client_factory()
            await client.connect()

            try:
                query = """
                    MATCH (n) WHERE n.qualified_name = $qn
                    OPTIONAL MATCH (m:File)-[*]-(n)
                    RETURN n.name AS name, n.start_line AS start, n.end_line AS end,
                           m.path AS path, n.docstring AS docstring
                    LIMIT 1
                """
                results = await client.execute(query, {"qn": qualified_name})

                if not results:
                    return CodeSnippet(
                        qualified_name=qualified_name,
                        found=False,
                        error_message="Entity not found in graph.",
                    )

                result = results[0]
                file_path = result.get("path")
                start_line = result.get("start")
                end_line = result.get("end")

                if not all([file_path, start_line, end_line]):
                    return CodeSnippet(
                        qualified_name=qualified_name,
                        file_path=file_path or "",
                        found=False,
                        error_message="Graph entry missing location data.",
                    )

                full_path = (project_root / file_path).resolve()
                if not full_path.is_relative_to(project_root.resolve()):
                    return CodeSnippet(
                        qualified_name=qualified_name,
                        file_path=file_path,
                        found=False,
                        error_message="Path traversal detected - access denied.",
                    )

                if not full_path.exists():
                    return CodeSnippet(
                        qualified_name=qualified_name,
                        file_path=file_path,
                        found=False,
                        error_message=f"Source file not found: {file_path}",
                    )

                try:
                    with full_path.open("r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except (OSError, PermissionError) as e:
                    return CodeSnippet(
                        qualified_name=qualified_name,
                        file_path=file_path,
                        found=False,
                        error_message=f"Failed to read file: {e}",
                    )

                source_code = "".join(lines[start_line - 1 : end_line])

                return CodeSnippet(
                    qualified_name=qualified_name,
                    source_code=source_code,
                    file_path=file_path,
                    line_start=start_line,
                    line_end=end_line,
                    docstring=result.get("docstring"),
                    found=True,
                )

            finally:
                await client.close()

        except Exception as e:
            logger.error(f"[Tool:GetCode] Error: {e}", exc_info=True)
            return CodeSnippet(
                qualified_name=qualified_name,
                found=False,
                error_message=str(e),
            )

    return {
        "name": "get_code_snippet",
        "description": (
            "Retrieve source code for a specific function, class, or method "
            "by its fully qualified name."
        ),
        "function": get_code_snippet,
        "parameters": {
            "qualified_name": {
                "type": "string",
                "description": "Full qualified name (e.g., 'myproject.models.User')",
                "required": True,
            },
        },
    }
