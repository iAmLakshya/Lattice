import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from lattice.shared.cache import FunctionRegistry
from lattice.infrastructure.qdrant import QdrantManager
from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.indexing.progress import ProgressTracker
from lattice.parsing.api import (
    CallProcessor,
    ImportProcessor,
    InheritanceTracker,
    ParsedFile,
    CodeParser,
)
from lattice.infrastructure.llm import BaseEmbeddingProvider
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

    max_workers: int = 4
    max_concurrent_api: int = 5
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
