from typing import Any

from lattice.shared.config.loader import get_config_value


class ChunkingConfig:
    min_chunk_size: int = get_config_value("chunking", "min_chunk_size", default=1)
    chunk_name_separator: str = get_config_value(
        "chunking", "chunk_name_separator", default="_part"
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
    default_max_tokens: int = get_config_value("summarization", "default_max_tokens", default=500)
    default_temperature: float = get_config_value(
        "summarization", "default_temperature", default=0.7
    )


class MetadataConfig:
    default_budget_usd: float = get_config_value("metadata", "default_budget_usd", default=0.50)
    default_retry_delay: float = get_config_value("metadata", "default_retry_delay", default=1.0)
    max_retries: int = get_config_value("metadata", "max_retries", default=2)

    @staticmethod
    def get_ignore_patterns() -> list[str]:
        return get_config_value("metadata", "ignore_patterns", "patterns", default=[])

    @staticmethod
    def get_field_config(field_name: str) -> dict[str, Any]:
        return get_config_value("metadata", "fields", field_name, default={})


class GraphConfig:
    default_batch_size: int = get_config_value("graph", "default_batch_size", default=1000)
    batch_size_multiplier: int = get_config_value("graph", "batch_size_multiplier", default=100)


class WatcherConfig:
    debounce_delay: float = get_config_value("watcher", "debounce_delay", default=0.5)
    observer_join_timeout: float = get_config_value("watcher", "observer_join_timeout", default=5.0)
    queue_get_timeout: float = get_config_value("watcher", "queue_get_timeout", default=1.0)


class DriftConfig:
    request_delay: float = get_config_value("drift", "request_delay", default=0.5)
    max_retries: int = get_config_value("drift", "max_retries", default=5)
    retry_exponential_base: int = get_config_value("drift", "retry_exponential_base", default=2)
    retry_exponential_multiplier: int = get_config_value(
        "drift", "retry_exponential_multiplier", default=2
    )
    retry_base_wait_offset: int = get_config_value("drift", "retry_base_wait_offset", default=5)


class MCPConfig:
    query_code_graph_default_limit: int = get_config_value(
        "mcp", "query_code_graph_default_limit", default=10
    )
    semantic_search_default_limit: int = get_config_value(
        "mcp", "semantic_search_default_limit", default=5
    )


class CachingConfig:
    max_entries: int = get_config_value("caching", "max_entries", default=1000)
    max_memory_mb: int = get_config_value("caching", "max_memory_mb", default=500)
    prompt_loader_cache_size: int = get_config_value(
        "caching", "prompt_loader_cache_size", default=32
    )
    config_loader_cache_size: int = get_config_value(
        "caching", "config_loader_cache_size", default=1
    )
    eviction_fraction: int = get_config_value("caching", "eviction_fraction", default=10)
    memory_pressure_threshold: float = get_config_value(
        "caching", "memory_pressure_threshold", default=0.8
    )
