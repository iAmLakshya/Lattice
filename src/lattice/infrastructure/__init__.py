"""Infrastructure adapters for external systems.

This module provides a unified entry point for all infrastructure adapters:
- memgraph: Graph database (Memgraph/Neo4j)
- qdrant: Vector database
- postgres: PostgreSQL database
- llm: LLM and embedding providers
"""

from lattice.infrastructure.llm import (
    BaseEmbeddingProvider,
    BaseLLMProvider,
    get_embedding_provider,
    get_llm_provider,
)
from lattice.infrastructure.memgraph import (
    BatchGraphBuilder,
    GraphBuilder,
    GraphSchema,
    MemgraphClient,
)
from lattice.infrastructure.postgres import PostgresClient
from lattice.infrastructure.qdrant import (
    CollectionName,
    QdrantManager,
    VectorIndexer,
    VectorSearcher,
    create_embedder,
)

__all__ = [
    # Memgraph
    "BatchGraphBuilder",
    "GraphBuilder",
    "GraphSchema",
    "MemgraphClient",
    # Qdrant
    "CollectionName",
    "QdrantManager",
    "VectorIndexer",
    "VectorSearcher",
    "create_embedder",
    # Postgres
    "PostgresClient",
    # LLM
    "BaseEmbeddingProvider",
    "BaseLLMProvider",
    "get_embedding_provider",
    "get_llm_provider",
]
