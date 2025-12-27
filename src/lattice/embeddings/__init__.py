"""Embeddings module for vector operations."""

from lattice.embeddings.chunker import CodeChunk, CodeChunker
from lattice.embeddings.client import CollectionName, QdrantManager
from lattice.embeddings.embedder import OpenAIEmbedder
from lattice.embeddings.indexer import (
    CodeSearchResult,
    SummarySearchResult,
    VectorIndexer,
    VectorSearcher,
)

__all__ = [
    "QdrantManager",
    "CollectionName",
    "OpenAIEmbedder",
    "CodeChunk",
    "CodeChunker",
    "VectorIndexer",
    "VectorSearcher",
    "CodeSearchResult",
    "SummarySearchResult",
]
