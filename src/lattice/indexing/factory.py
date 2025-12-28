import logging
import os
from collections.abc import Callable
from pathlib import Path

from lattice.indexing.orchestrator import PipelineOrchestrator
from lattice.infrastructure.memgraph import GraphSchema, MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager, create_embedder
from lattice.parsing.api import CodeParser, create_default_extractors
from lattice.shared.config import get_settings
from lattice.summarization.api import create_code_summarizer

logger = logging.getLogger(__name__)


async def create_pipeline_orchestrator(
    repo_path: str | Path,
    project_name: str | None = None,
    progress_callback: Callable | None = None,
    force: bool = False,
    skip_metadata: bool = False,
) -> PipelineOrchestrator:
    logger.info("Creating pipeline orchestrator with dependencies")

    settings = get_settings()
    max_workers = min(os.cpu_count() or 4, 8)
    max_concurrent_api = settings.indexing.max_concurrent_requests

    memgraph = MemgraphClient()
    await memgraph.connect()

    schema = GraphSchema(memgraph)
    await schema.setup()

    qdrant = QdrantManager()
    await qdrant.connect()
    await qdrant.create_collections()

    parser = CodeParser(extractors=create_default_extractors())
    embedder = create_embedder()
    summarizer = create_code_summarizer()

    logger.info(
        f"Pipeline initialized with {max_workers} workers, "
        f"{max_concurrent_api} concurrent API calls"
    )

    return PipelineOrchestrator(
        repo_path=repo_path,
        project_name=project_name,
        progress_callback=progress_callback,
        force=force,
        skip_metadata=skip_metadata,
        memgraph_client=memgraph,
        qdrant_client=qdrant,
        parser=parser,
        embedder=embedder,
        summarizer=summarizer,
        max_workers=max_workers,
        max_concurrent_api=max_concurrent_api,
    )
