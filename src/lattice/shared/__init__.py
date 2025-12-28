"""Shared cross-cutting concerns.

This module provides unified access to:
- config: Application configuration
- ports: Protocol definitions (abstract interfaces)
- exceptions: Domain exceptions
- types: Shared type definitions
- cache: Caching utilities
- protocols: Protocol definitions
"""

from __future__ import annotations

from lattice.shared.cache import ASTCache, BoundedCache, FunctionRegistry
from lattice.shared.config import Settings, get_settings
from lattice.shared.exceptions import (
    CodeRAGError,
    ConfigurationError,
    ConnectionError,
    EmbeddingError,
    GraphError,
    IndexingError,
    MetadataError,
    ParsingError,
    PostgresError,
    QueryError,
    SummarizationError,
    VectorStoreError,
)
from lattice.shared.ports import (
    EmbeddingProvider,
    GraphReader,
    GraphWriter,
    LLMProvider,
    VectorReader,
    VectorWriter,
)
from lattice.shared.protocols import (
    Chunker,
    Embedder,
    GraphClient,
    ProgressCallback,
    Repository,
    VectorStore,
)
from lattice.shared.protocols import LLMProvider as LLMProviderProtocol
from lattice.shared.types import (
    EntityType,
    Language,
    PipelineStage,
    QueryType,
    ResultSource,
)

__all__ = [
    # Ports
    "EmbeddingProvider",
    "GraphReader",
    "GraphWriter",
    "LLMProvider",
    "VectorReader",
    "VectorWriter",
    # Protocols
    "Chunker",
    "Embedder",
    "GraphClient",
    "LLMProviderProtocol",
    "ProgressCallback",
    "Repository",
    "VectorStore",
    # Config
    "Settings",
    "get_settings",
    # Exceptions
    "CodeRAGError",
    "ConfigurationError",
    "ConnectionError",
    "EmbeddingError",
    "GraphError",
    "IndexingError",
    "MetadataError",
    "ParsingError",
    "PostgresError",
    "QueryError",
    "SummarizationError",
    "VectorStoreError",
    # Types
    "EntityType",
    "Language",
    "PipelineStage",
    "QueryType",
    "ResultSource",
    # Cache
    "ASTCache",
    "BoundedCache",
    "FunctionRegistry",
]
