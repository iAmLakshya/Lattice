"""Semantic search tool for MCP."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from lattice.mcp.tools.models import SearchResult, ToolResult

logger = logging.getLogger(__name__)


def create_semantic_search_tool(
    vector_searcher_factory: Callable[..., Any],
) -> dict[str, Any]:
    """Create the semantic_search tool.

    Args:
        vector_searcher_factory: Factory function to create VectorSearcher.

    Returns:
        Tool definition dict for MCP registration.
    """

    async def semantic_search(
        query: str,
        limit: int = 5,
        entity_type: str | None = None,
    ) -> ToolResult:
        """Search for code by functionality or intent using natural language.

        Use this tool to find code that performs specific functionality
        based on intent rather than exact names. Perfect for exploratory
        questions about what code exists.

        Args:
            query: Natural language description of desired functionality.
            limit: Maximum number of results (default: 5).
            entity_type: Filter by type: "function", "class", "method" (optional).

        Returns:
            ToolResult with matching code entities.

        Examples:
            - "Find error handling functions"
            - "Authentication related code"
            - "Database query implementations"
            - "File I/O operations"
        """
        logger.info(f"[Tool:SemanticSearch] Query: '{query}'")

        try:
            searcher = vector_searcher_factory()
            results = await searcher.search_code(
                query=query,
                limit=limit,
                entity_type=entity_type,
            )

            search_results = [
                SearchResult(
                    qualified_name=r.entity_name,
                    entity_type=r.entity_type,
                    file_path=r.file_path,
                    score=r.score,
                    summary=r.summary,
                )
                for r in results
            ]

            return ToolResult(
                success=True,
                data=[vars(r) for r in search_results],
                message=f"Found {len(search_results)} matches for '{query}'.",
            )

        except Exception as e:
            logger.error(f"[Tool:SemanticSearch] Error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                error=str(e),
            )

    return {
        "name": "semantic_search",
        "description": (
            "Search for code by functionality or intent using natural language. "
            "Find code based on what it does, not its name."
        ),
        "function": semantic_search,
        "parameters": {
            "query": {
                "type": "string",
                "description": "Natural language description of functionality",
                "required": True,
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (default: 5)",
                "required": False,
            },
            "entity_type": {
                "type": "string",
                "description": "Filter by type: function, class, method",
                "required": False,
            },
        },
    }
