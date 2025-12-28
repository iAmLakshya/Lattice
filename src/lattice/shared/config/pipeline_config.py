from lattice.shared.config.loader import get_config_value


class PipelineConfig:
    stage_weight_scanning: int = get_config_value("pipeline", "stage_weight_scanning", default=5)
    stage_weight_parsing: int = get_config_value("pipeline", "stage_weight_parsing", default=15)
    stage_weight_building_graph: int = get_config_value(
        "pipeline", "stage_weight_building_graph", default=20
    )
    stage_weight_summarizing: int = get_config_value(
        "pipeline", "stage_weight_summarizing", default=25
    )
    stage_weight_metadata: int = get_config_value("pipeline", "stage_weight_metadata", default=10)
    stage_weight_embedding: int = get_config_value("pipeline", "stage_weight_embedding", default=25)


class PipelineRuntimeConfig:
    max_workers: int = get_config_value("pipeline", "max_workers", default=4)
    max_concurrent_api: int = get_config_value("pipeline", "max_concurrent_api", default=5)


class IndexingConfig:
    embed_max_retries: int = get_config_value("indexing", "embed_max_retries", default=3)
    embed_batch_divisor: int = get_config_value("indexing", "embed_batch_divisor", default=3)
    summarize_max_retries: int = get_config_value("indexing", "summarize_max_retries", default=3)
    retry_wait_multiplier: int = get_config_value("indexing", "retry_wait_multiplier", default=2)
    api_batch_size: int = get_config_value("indexing", "api_batch_size", default=3)
