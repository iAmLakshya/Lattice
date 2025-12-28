"""Query code graph tool for MCP."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from lattice.mcp.tools.models import ToolResult

logger = logging.getLogger(__name__)


def create_query_tool(
    query_engine_factory: Callable[..., Any],
) -> dict[str, Any]:
    """Create the query_code_graph tool.

    Args:
        query_engine_factory: Factory function to create QueryEngine.

    Returns:
        Tool definition dict for MCP registration.
    """

    async def query_code_graph(
        question: str,
        limit: int = 10,
    ) -> ToolResult:
        """Query the codebase using natural language.

        Ask questions about the codebase structure, functionality, relationships,
        or implementation details. The tool uses hybrid search (graph + vector)
        and generates an AI response based on relevant code.

        Args:
            question: Natural language question about the codebase.
            limit: Maximum number of search results to use (default: 10).

        Returns:
            ToolResult with the answer and sources.

        Examples:
            - "How does authentication work?"
            - "What functions call the User class?"
            - "Explain the payment processing flow"
            - "Where is error handling implemented?"
        """
        logger.info(f"[Tool:Query] Question: '{question}'")

        try:
            engine = query_engine_factory()
            result = await engine.query(question, limit=limit)

            sources = [
                {
                    "file": s.file_path,
                    "entity": s.entity_name,
                    "line": s.start_line,
                }
                for s in result.sources[:5]
            ]

            return ToolResult(
                success=True,
                data={
                    "answer": result.answer,
                    "sources": sources,
                    "query_type": result.query_analysis.query_type.value
                    if result.query_analysis
                    else None,
                },
                message=f"Found {len(result.sources)} relevant code sections.",
            )

        except Exception as e:
            logger.error(f"[Tool:Query] Error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=str(e),
            )

    return {
        "name": "query_code_graph",
        "description": (
            "Query the codebase using natural language. Ask about structure, "
            "functionality, relationships, or implementation details."
        ),
        "function": query_code_graph,
        "parameters": {
            "question": {
                "type": "string",
                "description": "Natural language question about the codebase",
                "required": True,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum search results to use (default: 10)",
                "required": False,
            },
        },
    }
