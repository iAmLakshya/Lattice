import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from lattice.indexing.progress import ProgressTracker
from lattice.infrastructure.llm import BaseEmbeddingProvider
from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager
from lattice.parsing.api import (
    CallProcessor,
    CodeParser,
    ImportProcessor,
    InheritanceTracker,
    ParsedFile,
)
from lattice.shared.cache import FunctionRegistry
from lattice.shared.config import PipelineRuntimeConfig
from lattice.summarization.api import CodeSummarizer


@dataclass
class PipelineContext:
    repo_path: Path
    project_name: str
    tracker: ProgressTracker
    memgraph: MemgraphClient
    qdrant: QdrantManager
    parser: CodeParser
    embedder: BaseEmbeddingProvider
    summarizer: CodeSummarizer

    max_workers: int = PipelineRuntimeConfig.max_workers
    max_concurrent_api: int = PipelineRuntimeConfig.max_concurrent_api
    force: bool = False
    skip_metadata: bool = False

    graph_semaphore: asyncio.Semaphore | None = None
    api_semaphore: asyncio.Semaphore | None = None

    function_registry: FunctionRegistry = field(default_factory=FunctionRegistry)
    import_processor: ImportProcessor | None = None
    inheritance_tracker: InheritanceTracker | None = None
    call_processor: CallProcessor | None = None

    parsed_files: list[ParsedFile] = field(default_factory=list)
    file_update_status: dict[str, bool] = field(default_factory=dict)
    scanned_files: list = field(default_factory=list)
