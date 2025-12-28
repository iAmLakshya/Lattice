"""Index repository tool for MCP."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lattice.mcp.tools.models import ToolResult

logger = logging.getLogger(__name__)


def create_index_tool(
    orchestrator_factory: Callable[..., Any],
) -> dict[str, Any]:
    """Create the index_repository tool.

    Args:
        orchestrator_factory: Factory function to create PipelineOrchestrator.

    Returns:
        Tool definition dict for MCP registration.
    """

    async def index_repository(
        repo_path: str,
        project_name: str | None = None,
    ) -> ToolResult:
        """Index a codebase into the knowledge graph and vector store.

        This tool scans a repository, parses the code, builds a knowledge graph
        of code relationships, generates AI summaries, and creates embeddings
        for semantic search.

        Args:
            repo_path: Path to the repository to index.
            project_name: Optional name for the project. Defaults to directory name.

        Returns:
            ToolResult with indexing statistics.
        """
        logger.info(f"[Tool:Index] Indexing repository: {repo_path}")

        try:
            path = Path(repo_path).resolve()
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f"Repository path does not exist: {repo_path}",
                )

            name = project_name or path.name
            orchestrator = orchestrator_factory(path, name)

            stats = await orchestrator.run()

            return ToolResult(
                success=True,
                data=stats,
                message=f"Successfully indexed {stats.get('files_indexed', 0)} files "
                f"with {stats.get('entities_found', 0)} entities.",
            )

        except Exception as e:
            logger.error(f"[Tool:Index] Error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=str(e),
            )

    return {
        "name": "index_repository",
        "description": (
            "Index a codebase into the knowledge graph and vector store. "
            "Parses code, builds relationships, generates summaries, and creates embeddings."
        ),
        "function": index_repository,
        "parameters": {
            "repo_path": {
                "type": "string",
                "description": "Path to the repository to index",
                "required": True,
            },
            "project_name": {
                "type": "string",
                "description": "Optional project name (defaults to directory name)",
                "required": False,
            },
        },
    }
