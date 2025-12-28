import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

from lattice.indexing.context import PipelineContext
from lattice.indexing.progress import ProgressTracker
from lattice.indexing.stages import (
    EmbedStage,
    GraphBuildStage,
    MetadataStage,
    ParseStage,
    ScanStage,
    SummarizeStage,
)
from lattice.infrastructure.llm import BaseEmbeddingProvider
from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager
from lattice.parsing.api import CodeParser, ImportProcessor, InheritanceTracker
from lattice.shared.cache import FunctionRegistry
from lattice.shared.exceptions import IndexingError
from lattice.summarization.api import CodeSummarizer

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(
        self,
        repo_path: str | Path,
        project_name: str | None,
        progress_callback: Callable | None,
        force: bool,
        skip_metadata: bool,
        memgraph_client: MemgraphClient,
        qdrant_client: QdrantManager,
        parser: CodeParser,
        embedder: BaseEmbeddingProvider,
        summarizer: CodeSummarizer,
        max_workers: int,
        max_concurrent_api: int,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.project_name = project_name or self.repo_path.name
        self.force = force
        self.skip_metadata = skip_metadata

        self.tracker = ProgressTracker()
        if progress_callback:
            self.tracker.add_callback(progress_callback)

        self._memgraph = memgraph_client
        self._qdrant = qdrant_client
        self._parser = parser
        self._embedder = embedder
        self._summarizer = summarizer
        self._max_workers = max_workers
        self._max_concurrent_api = max_concurrent_api

        self._stages = [
            ScanStage(),
            ParseStage(),
            GraphBuildStage(),
            SummarizeStage(),
            MetadataStage(),
            EmbedStage(),
        ]

    def _create_context(self) -> PipelineContext:
        graph_semaphore = asyncio.Semaphore(self._max_concurrent_api)
        api_semaphore = asyncio.Semaphore(self._max_concurrent_api)

        function_registry = FunctionRegistry()
        import_processor = ImportProcessor(
            function_registry=function_registry,
            project_name=self.project_name,
            repo_path=self.repo_path,
        )
        inheritance_tracker = InheritanceTracker(
            function_registry=function_registry,
            import_processor=import_processor,
        )

        return PipelineContext(
            repo_path=self.repo_path,
            project_name=self.project_name,
            tracker=self.tracker,
            memgraph=self._memgraph,
            qdrant=self._qdrant,
            parser=self._parser,
            embedder=self._embedder,
            summarizer=self._summarizer,
            max_workers=self._max_workers,
            max_concurrent_api=self._max_concurrent_api,
            force=self.force,
            skip_metadata=self.skip_metadata,
            graph_semaphore=graph_semaphore,
            api_semaphore=api_semaphore,
            function_registry=function_registry,
            import_processor=import_processor,
            inheritance_tracker=inheritance_tracker,
        )

    async def _cleanup(self) -> None:
        if self._memgraph:
            try:
                await self._memgraph.close()
            except Exception as e:
                logger.warning(f"Failed to close Memgraph connection: {e}")

        if self._qdrant:
            try:
                await self._qdrant.close()
            except Exception as e:
                logger.warning(f"Failed to close Qdrant connection: {e}")

    async def run(self) -> dict:
        try:
            self.tracker.start()
            logger.info(f"Starting indexing pipeline for {self.project_name}")

            ctx = self._create_context()

            for stage in self._stages:
                if stage.name == "metadata" and ctx.skip_metadata:
                    continue
                await stage.execute(ctx)

            self.tracker.complete()
            logger.info(f"Pipeline completed successfully for {self.project_name}")

            return {
                "files_indexed": self.tracker.progress.files_parsed,
                "entities_found": self.tracker.progress.entities_found,
                "graph_nodes": self.tracker.progress.graph_nodes_created,
                "summaries": self.tracker.progress.summaries_generated,
                "chunks_embedded": self.tracker.progress.chunks_embedded,
                "elapsed_seconds": self.tracker.progress.elapsed_time,
            }

        except Exception as e:
            error_msg = f"Pipeline failed: {e}"
            logger.error(error_msg, exc_info=True)
            self.tracker.error(error_msg)
            raise IndexingError(error_msg, cause=e)
        finally:
            await self._cleanup()
