"""Data models for MCP tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standard result format for MCP tools."""

    success: bool
    data: Any = None
    message: str = ""
    error: str | None = None


@dataclass
class CodeSnippet:
    """Result from code retrieval tool."""

    qualified_name: str
    source_code: str = ""
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    docstring: str | None = None
    found: bool = True
    error_message: str | None = None


@dataclass
class SearchResult:
    """Result from semantic search tool."""

    qualified_name: str
    entity_type: str
    file_path: str
    score: float
    summary: str | None = None


@dataclass
class GraphQueryResult:
    """Result from graph query tool."""

    query_used: str
    results: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
