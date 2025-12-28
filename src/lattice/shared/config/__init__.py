"""Configuration module for Lattice."""

from lattice.shared.config.documents_config import (
    DocumentsConfig,
    DriftDetectorConfig,
    LinkFinderConfig,
    ReferenceExtractionConfig,
)
from lattice.shared.config.loader import (
    get_config_value,
    load_defaults,
)
from lattice.shared.config.misc_config import (
    CachingConfig,
    ChunkingConfig,
    DriftConfig,
    GraphConfig,
    MCPConfig,
    MetadataConfig,
    SummarizationConfig,
    WatcherConfig,
)
from lattice.shared.config.pipeline_config import (
    IndexingConfig,
    PipelineConfig,
    PipelineRuntimeConfig,
)
from lattice.shared.config.providers_config import (
    OllamaConfig,
    ProvidersConfig,
)
from lattice.shared.config.query_config import (
    QueryConfig,
    QueryContextConfig,
    QueryReasoningConfig,
)
from lattice.shared.config.ranking_config import (
    RankingConfig,
    RerankerConfig,
    ScorerConfig,
)
from lattice.shared.config.settings import (
    AISettings,
    DatabaseSettings,
    FileSettings,
    IndexingSettings,
    MetadataSettings,
    PostgresSettings,
    QuerySettings,
    Settings,
    get_settings,
)

__all__ = [
    # Settings classes
    "AISettings",
    "DatabaseSettings",
    "FileSettings",
    "IndexingSettings",
    "MetadataSettings",
    "PostgresSettings",
    "QuerySettings",
    "Settings",
    "get_settings",
    # Config classes from split files
    "CachingConfig",
    "ChunkingConfig",
    "DocumentsConfig",
    "DriftConfig",
    "DriftDetectorConfig",
    "GraphConfig",
    "IndexingConfig",
    "LinkFinderConfig",
    "MCPConfig",
    "MetadataConfig",
    "OllamaConfig",
    "PipelineConfig",
    "PipelineRuntimeConfig",
    "ProvidersConfig",
    "QueryConfig",
    "QueryContextConfig",
    "QueryReasoningConfig",
    "RankingConfig",
    "ReferenceExtractionConfig",
    "RerankerConfig",
    "ScorerConfig",
    "SummarizationConfig",
    "WatcherConfig",
    "get_config_value",
    "load_defaults",
]
