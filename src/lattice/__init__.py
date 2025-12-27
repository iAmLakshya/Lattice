"""Lattice - A hybrid RAG system for code repositories."""

__version__ = "0.1.0"

from lattice.config import Settings, get_settings
from lattice.pipeline.orchestrator import PipelineOrchestrator, run_indexing
from lattice.query import QueryEngine, QueryResult

__all__ = [
    "get_settings",
    "PipelineOrchestrator",
    "QueryEngine",
    "QueryResult",
    "run_indexing",
    "Settings",
]
