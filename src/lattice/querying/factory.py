import logging

from lattice.infrastructure.qdrant import QdrantManager
from lattice.infrastructure.qdrant.embedder import create_embedder
from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.querying.context import ContextBuilder
from lattice.querying.engine import QueryEngine
from lattice.querying.graph_reasoning import GraphReasoningEngine
from lattice.querying.query_planner import QueryPlanner
from lattice.querying.ranking import HybridRanker, RankingConfig
from lattice.querying.responder import ResponseGenerator
from lattice.querying.vector_search import VectorSearcher

logger = logging.getLogger(__name__)


async def create_query_engine() -> QueryEngine:
    logger.info("Creating query engine with dependencies")

    memgraph = MemgraphClient()
    await memgraph.connect()

    qdrant = QdrantManager()
    await qdrant.connect()

    embedder = create_embedder()

    return QueryEngine(
        memgraph=memgraph,
        qdrant=qdrant,
        planner=QueryPlanner(),
        graph_engine=GraphReasoningEngine(memgraph),
        vector_searcher=VectorSearcher(qdrant, embedder),
        context_builder=ContextBuilder(memgraph, qdrant),
        ranker=HybridRanker(RankingConfig()),
        responder=ResponseGenerator(),
    )
