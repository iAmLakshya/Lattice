import logging

from lattice.documents.service import DocumentService
from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.postgres import create_postgres_client
from lattice.infrastructure.qdrant import QdrantManager, create_embedder

logger = logging.getLogger(__name__)


async def create_document_service(
    include_memgraph: bool = True,
) -> DocumentService:
    logger.info("Creating document service with dependencies")

    postgres = create_postgres_client()
    await postgres.connect()

    qdrant = QdrantManager()
    await qdrant.connect()

    embedder = create_embedder()

    memgraph = None
    if include_memgraph:
        memgraph = MemgraphClient()
        await memgraph.connect()

    return DocumentService(postgres, qdrant, embedder, memgraph)
