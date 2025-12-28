import logging

from lattice.infrastructure.llm import get_llm_provider
from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager, create_embedder
from lattice.querying.context import ContextBuilder
from lattice.querying.engine import QueryEngine
from lattice.querying.graph_reasoning import GraphReasoningEngine
from lattice.querying.query_planner import QueryPlanner
from lattice.querying.ranking import HybridRanker, RankingConfig
from lattice.querying.response_builder import ResponseBuilder
from lattice.querying.search_coordinator import SearchCoordinator
from lattice.querying.vector_search import VectorSearcher

logger = logging.getLogger(__name__)


async def create_query_engine() -> QueryEngine:
    logger.info("Creating query engine with dependencies")

    memgraph = MemgraphClient()
    await memgraph.connect()

    qdrant = QdrantManager()
    await qdrant.connect()

    embedder = create_embedder()
    llm_provider = get_llm_provider()

    vector_searcher = VectorSearcher(qdrant, embedder)
    graph_engine = GraphReasoningEngine(memgraph)

    return QueryEngine(
        memgraph=memgraph,
        qdrant=qdrant,
        planner=QueryPlanner(llm_provider=llm_provider),
        graph_engine=graph_engine,
        context_builder=ContextBuilder(memgraph, qdrant),
        ranker=HybridRanker(RankingConfig()),
        response_builder=ResponseBuilder(llm_provider),
        search_coordinator=SearchCoordinator(vector_searcher, graph_engine),
    )
