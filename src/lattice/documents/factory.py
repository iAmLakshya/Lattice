import logging

from lattice.infrastructure.postgres.postgres import PostgresClient
from lattice.documents.service import DocumentService
from lattice.infrastructure.qdrant import QdrantManager
from lattice.infrastructure.qdrant.embedder import create_embedder
from lattice.infrastructure.memgraph.client import MemgraphClient

logger = logging.getLogger(__name__)


async def create_document_service(
    include_memgraph: bool = True,
) -> DocumentService:
    logger.info("Creating document service with dependencies")

    postgres = PostgresClient()
    await postgres.connect()

    qdrant = QdrantManager()
    await qdrant.connect()

    embedder = create_embedder()

    memgraph = None
    if include_memgraph:
        memgraph = MemgraphClient()
        await memgraph.connect()

    return DocumentService(postgres, qdrant, embedder, memgraph)
