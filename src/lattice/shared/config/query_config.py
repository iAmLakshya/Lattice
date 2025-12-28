from lattice.shared.config.loader import get_config_value


class QueryConfig:
    max_context_results: int = get_config_value("query", "max_context_results", default=10)
    max_content_length: int = get_config_value("query", "max_content_length", default=2000)
    default_search_limit: int = get_config_value("query", "default_search_limit", default=15)
    default_max_depth: int = get_config_value("query", "default_max_depth", default=2)
    related_entities_limit: int = get_config_value("query", "related_entities_limit", default=20)
    exclude_file_buffer: int = get_config_value("query", "exclude_file_buffer", default=5)
    planning_temperature: float = get_config_value("query", "planning_temperature", default=0.0)
    planning_max_tokens: int = get_config_value("query", "planning_max_tokens", default=2000)
    completion_max_tokens: int = get_config_value("query", "completion_max_tokens", default=2000)
    fallback_max_hops: int = get_config_value("query", "fallback_max_hops", default=3)


class QueryReasoningConfig:
    max_traversal_depth: int = get_config_value(
        "query", "reasoning", "max_traversal_depth", default=5
    )
    max_results_per_query: int = get_config_value(
        "query", "reasoning", "max_results_per_query", default=50
    )
    max_path_length: int = get_config_value("query", "reasoning", "max_path_length", default=10)
    max_related_entities: int = get_config_value(
        "query", "reasoning", "max_related_entities", default=30
    )
    comprehensive_max_hops: int = get_config_value(
        "query", "reasoning", "comprehensive_max_hops", default=2
    )
    comprehensive_limit: int = get_config_value(
        "query", "reasoning", "comprehensive_limit", default=10
    )
    max_call_chain_results: int = get_config_value(
        "query", "reasoning", "max_call_chain_results", default=5
    )
    max_path_results: int = get_config_value("query", "reasoning", "max_path_results", default=10)


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
    entity_code_search_limit: int = get_config_value(
        "query", "context", "entity_code_search_limit", default=1
    )
    max_docstring_summary_length: int = get_config_value(
        "query", "context", "max_docstring_summary_length", default=500
    )
    max_related_entities_per_context: int = get_config_value(
        "query", "context", "max_related_entities_per_context", default=10
    )
    max_callers_displayed: int = get_config_value(
        "query", "context", "max_callers_displayed", default=5
    )
    max_callees_displayed: int = get_config_value(
        "query", "context", "max_callees_displayed", default=5
    )
    max_files_for_summaries: int = get_config_value(
        "query", "context", "max_files_for_summaries", default=10
    )
