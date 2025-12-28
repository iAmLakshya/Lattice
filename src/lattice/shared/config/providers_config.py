from lattice.shared.config.loader import get_config_value


class ProvidersConfig:
    retry_max_attempts: int = get_config_value("providers", "retry_max_attempts", default=5)
    retry_multiplier: int = get_config_value("providers", "retry_multiplier", default=1)
    retry_min_wait: int = get_config_value("providers", "retry_min_wait", default=1)
    retry_max_wait: int = get_config_value("providers", "retry_max_wait", default=60)
    default_concurrency: int = get_config_value("providers", "default_concurrency", default=5)
    default_batch_size: int = get_config_value("providers", "default_batch_size", default=100)


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
