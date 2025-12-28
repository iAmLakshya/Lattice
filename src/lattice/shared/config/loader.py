import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULTS_PATH = Path(__file__).parent / "defaults.toml"


@lru_cache(maxsize=1)
def load_defaults() -> dict[str, Any]:
    with DEFAULTS_PATH.open("rb") as f:
        return tomllib.load(f)


def get_config_value(*keys: str, default: Any = None) -> Any:
    config = load_defaults()
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


class ChunkingConfig:
    min_chunk_size: int = get_config_value("chunking", "min_chunk_size", default=1)
    chunk_name_separator: str = get_config_value(
        "chunking", "chunk_name_separator", default="_part"
    )


class QueryConfig:
    max_context_results: int = get_config_value(
        "query", "max_context_results", default=10
    )
    max_content_length: int = get_config_value(
        "query", "max_content_length", default=2000
    )
    default_search_limit: int = get_config_value(
        "query", "default_search_limit", default=10
    )
    default_max_depth: int = get_config_value("query", "default_max_depth", default=2)
    related_entities_limit: int = get_config_value(
        "query", "related_entities_limit", default=20
    )
    exclude_file_buffer: int = get_config_value(
        "query", "exclude_file_buffer", default=5
    )


class QueryReasoningConfig:
    max_traversal_depth: int = get_config_value(
        "query", "reasoning", "max_traversal_depth", default=5
    )
    max_results_per_query: int = get_config_value(
        "query", "reasoning", "max_results_per_query", default=50
    )
    max_path_length: int = get_config_value(
        "query", "reasoning", "max_path_length", default=10
    )
    max_related_entities: int = get_config_value(
        "query", "reasoning", "max_related_entities", default=30
    )
    comprehensive_max_hops: int = get_config_value(
        "query", "reasoning", "comprehensive_max_hops", default=2
    )
    comprehensive_limit: int = get_config_value(
        "query", "reasoning", "comprehensive_limit", default=10
    )


class QueryContextConfig:
    max_code_snippet_length: int = get_config_value(
        "query", "context", "max_code_snippet_length", default=3000
    )
    max_context_entities: int = get_config_value(
        "query", "context", "max_context_entities", default=20
    )
    max_related_code_snippets: int = get_config_value(
        "query", "context", "max_related_code_snippets", default=5
    )


class RankingConfig:
    default_graph_weight: float = get_config_value(
        "ranking", "default_graph_weight", default=0.5
    )
    default_vector_weight: float = get_config_value(
        "ranking", "default_vector_weight", default=0.5
    )
    default_centrality_weight: float = get_config_value(
        "ranking", "default_centrality_weight", default=0.2
    )
    default_context_weight: float = get_config_value(
        "ranking", "default_context_weight", default=0.1
    )
    entity_match_bonus: float = get_config_value(
        "ranking", "entity_match_bonus", default=0.3
    )
    relationship_bonus: float = get_config_value(
        "ranking", "relationship_bonus", default=0.15
    )
    max_results_per_file: int = get_config_value(
        "ranking", "max_results_per_file", default=5
    )
    max_total_results: int = get_config_value(
        "ranking", "max_total_results", default=50
    )


class RerankerConfig:
    graph_weight: float = get_config_value(
        "ranking", "reranker", "graph_weight", default=0.4
    )
    vector_weight: float = get_config_value(
        "ranking", "reranker", "vector_weight", default=0.6
    )
    max_results_per_file: int = get_config_value(
        "ranking", "reranker", "max_results_per_file", default=3
    )


class SummarizationConfig:
    file_code_max_chars: int = get_config_value(
        "summarization", "file_code_max_chars", default=8000
    )
    function_code_max_chars: int = get_config_value(
        "summarization", "function_code_max_chars", default=4000
    )
    class_code_max_chars: int = get_config_value(
        "summarization", "class_code_max_chars", default=6000
    )
    default_max_tokens: int = get_config_value(
        "summarization", "default_max_tokens", default=500
    )
    default_temperature: float = get_config_value(
        "summarization", "default_temperature", default=0.7
    )


class PipelineConfig:
    stage_weight_scanning: int = get_config_value(
        "pipeline", "stage_weight_scanning", default=5
    )
    stage_weight_parsing: int = get_config_value(
        "pipeline", "stage_weight_parsing", default=15
    )
    stage_weight_building_graph: int = get_config_value(
        "pipeline", "stage_weight_building_graph", default=20
    )
    stage_weight_summarizing: int = get_config_value(
        "pipeline", "stage_weight_summarizing", default=25
    )
    stage_weight_metadata: int = get_config_value(
        "pipeline", "stage_weight_metadata", default=10
    )
    stage_weight_embedding: int = get_config_value(
        "pipeline", "stage_weight_embedding", default=25
    )


class ProvidersConfig:
    retry_max_attempts: int = get_config_value(
        "providers", "retry_max_attempts", default=5
    )
    retry_multiplier: int = get_config_value(
        "providers", "retry_multiplier", default=1
    )
    retry_min_wait: int = get_config_value("providers", "retry_min_wait", default=1)
    retry_max_wait: int = get_config_value("providers", "retry_max_wait", default=60)
    default_concurrency: int = get_config_value(
        "providers", "default_concurrency", default=5
    )
    default_batch_size: int = get_config_value(
        "providers", "default_batch_size", default=100
    )


class OllamaConfig:
    base_url: str = get_config_value(
        "providers", "ollama", "base_url", default="http://localhost:11434/v1"
    )
    default_llm_model: str = get_config_value(
        "providers", "ollama", "default_llm_model", default="llama3.2"
    )
    default_embedding_model: str = get_config_value(
        "providers", "ollama", "default_embedding_model", default="nomic-embed-text"
    )


class MetadataConfig:
    default_budget_usd: float = get_config_value(
        "metadata", "default_budget_usd", default=0.50
    )
    default_retry_delay: float = get_config_value(
        "metadata", "default_retry_delay", default=1.0
    )
    max_retries: int = get_config_value("metadata", "max_retries", default=2)

    @staticmethod
    def get_ignore_patterns() -> list[str]:
        return get_config_value("metadata", "ignore_patterns", "patterns", default=[])

    @staticmethod
    def get_field_config(field_name: str) -> dict[str, Any]:
        return get_config_value("metadata", "fields", field_name, default={})


class DocumentsConfig:
    scanner_extensions: list[str] = get_config_value(
        "documents", "scanner_extensions", default=[".md", ".mdx", ".rst", ".txt"]
    )
    scanner_ignore: list[str] = get_config_value(
        "documents", "scanner_ignore", default=[]
    )


class ReferenceExtractionConfig:
    backtick_qualified_confidence: float = get_config_value(
        "documents", "reference_extraction", "backtick_qualified_confidence", default=0.90
    )
    backtick_simple_confidence: float = get_config_value(
        "documents", "reference_extraction", "backtick_simple_confidence", default=0.80
    )
    class_name_confidence: float = get_config_value(
        "documents", "reference_extraction", "class_name_confidence", default=0.60
    )
    function_call_confidence: float = get_config_value(
        "documents", "reference_extraction", "function_call_confidence", default=0.50
    )
    python_def_confidence: float = get_config_value(
        "documents", "reference_extraction", "python_def_confidence", default=0.95
    )
    python_class_confidence: float = get_config_value(
        "documents", "reference_extraction", "python_class_confidence", default=0.95
    )
    js_function_confidence: float = get_config_value(
        "documents", "reference_extraction", "js_function_confidence", default=0.95
    )
    import_from_confidence: float = get_config_value(
        "documents", "reference_extraction", "import_from_confidence", default=0.85
    )


class LinkFinderConfig:
    relevance_high: float = get_config_value(
        "documents", "link_finder", "relevance_high", default=0.90
    )
    relevance_medium: float = get_config_value(
        "documents", "link_finder", "relevance_medium", default=0.70
    )
    relevance_low: float = get_config_value(
        "documents", "link_finder", "relevance_low", default=0.50
    )
    candidate_limit: int = get_config_value(
        "documents", "link_finder", "candidate_limit", default=20
    )
    content_preview_length: int = get_config_value(
        "documents", "link_finder", "content_preview_length", default=300
    )
    entity_list_limit: int = get_config_value(
        "documents", "link_finder", "entity_list_limit", default=15
    )
    doc_content_max: int = get_config_value(
        "documents", "link_finder", "doc_content_max", default=2500
    )
    max_tokens: int = get_config_value(
        "documents", "link_finder", "max_tokens", default=1000
    )


class DriftDetectorConfig:
    doc_content_max: int = get_config_value(
        "documents", "drift_detector", "doc_content_max", default=3000
    )
    code_content_max: int = get_config_value(
        "documents", "drift_detector", "code_content_max", default=4000
    )
    excerpt_length: int = get_config_value(
        "documents", "drift_detector", "excerpt_length", default=500
    )
    max_tokens: int = get_config_value(
        "documents", "drift_detector", "max_tokens", default=1500
    )
    default_drift_score: float = get_config_value(
        "documents", "drift_detector", "default_drift_score", default=0.5
    )


class GraphConfig:
    default_batch_size: int = get_config_value(
        "graph", "default_batch_size", default=1000
    )


class IndexingConfig:
    embed_max_retries: int = get_config_value(
        "indexing", "embed_max_retries", default=3
    )
    embed_batch_divisor: int = get_config_value(
        "indexing", "embed_batch_divisor", default=3
    )
    summarize_max_retries: int = get_config_value(
        "indexing", "summarize_max_retries", default=3
    )


class WatcherConfig:
    debounce_delay: float = get_config_value(
        "watcher", "debounce_delay", default=0.5
    )
    observer_join_timeout: float = get_config_value(
        "watcher", "observer_join_timeout", default=5.0
    )
    queue_get_timeout: float = get_config_value(
        "watcher", "queue_get_timeout", default=1.0
    )


class DriftConfig:
    request_delay: float = get_config_value("drift", "request_delay", default=0.5)
    max_retries: int = get_config_value("drift", "max_retries", default=5)
