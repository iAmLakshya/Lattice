from lattice.shared.config.loader import get_config_value


class RankingConfig:
    default_graph_weight: float = get_config_value("ranking", "default_graph_weight", default=0.5)
    default_vector_weight: float = get_config_value("ranking", "default_vector_weight", default=0.5)
    default_centrality_weight: float = get_config_value(
        "ranking", "default_centrality_weight", default=0.2
    )
    default_context_weight: float = get_config_value(
        "ranking", "default_context_weight", default=0.1
    )
    entity_match_bonus: float = get_config_value("ranking", "entity_match_bonus", default=0.3)
    relationship_bonus: float = get_config_value("ranking", "relationship_bonus", default=0.15)
    max_results_per_file: int = get_config_value("ranking", "max_results_per_file", default=5)
    max_total_results: int = get_config_value("ranking", "max_total_results", default=50)


class RerankerConfig:
    graph_weight: float = get_config_value("ranking", "reranker", "graph_weight", default=0.4)
    vector_weight: float = get_config_value("ranking", "reranker", "vector_weight", default=0.6)
    max_results_per_file: int = get_config_value(
        "ranking", "reranker", "max_results_per_file", default=3
    )


class ScorerConfig:
    min_depth_score: float = get_config_value("ranking", "scorer", "min_depth_score", default=0.3)
    depth_decay_rate: float = get_config_value("ranking", "scorer", "depth_decay_rate", default=0.2)
    partial_entity_match_score: float = get_config_value(
        "ranking", "scorer", "partial_entity_match_score", default=0.5
    )
    relationship_score_primary: float = get_config_value(
        "ranking", "scorer", "relationship_score_primary", default=1.0
    )
    relationship_score_caller: float = get_config_value(
        "ranking", "scorer", "relationship_score_caller", default=0.8
    )
    relationship_score_callee: float = get_config_value(
        "ranking", "scorer", "relationship_score_callee", default=0.7
    )
    relationship_score_default: float = get_config_value(
        "ranking", "scorer", "relationship_score_default", default=0.5
    )
    centrality_normalization_factor: int = get_config_value(
        "ranking", "scorer", "centrality_normalization_factor", default=50
    )
    context_score_summary: float = get_config_value(
        "ranking", "scorer", "context_score_summary", default=0.3
    )
    context_score_docstring: float = get_config_value(
        "ranking", "scorer", "context_score_docstring", default=0.2
    )
    context_score_signature: float = get_config_value(
        "ranking", "scorer", "context_score_signature", default=0.2
    )
    context_score_content: float = get_config_value(
        "ranking", "scorer", "context_score_content", default=0.3
    )
    quality_optimal_min_chars: int = get_config_value(
        "ranking", "scorer", "quality_optimal_min_chars", default=100
    )
    quality_optimal_max_chars: int = get_config_value(
        "ranking", "scorer", "quality_optimal_max_chars", default=2000
    )
    quality_acceptable_min_chars: int = get_config_value(
        "ranking", "scorer", "quality_acceptable_min_chars", default=50
    )
    quality_acceptable_max_chars: int = get_config_value(
        "ranking", "scorer", "quality_acceptable_max_chars", default=3000
    )
    quality_score_optimal: float = get_config_value(
        "ranking", "scorer", "quality_score_optimal", default=0.8
    )
    quality_score_acceptable: float = get_config_value(
        "ranking", "scorer", "quality_score_acceptable", default=0.5
    )
    quality_score_poor: float = get_config_value(
        "ranking", "scorer", "quality_score_poor", default=0.3
    )
    code_quality_weight: float = get_config_value(
        "ranking", "scorer", "code_quality_weight", default=0.1
    )
