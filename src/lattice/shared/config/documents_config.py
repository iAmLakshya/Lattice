from lattice.shared.config.loader import get_config_value


class DocumentsConfig:
    scanner_extensions: list[str] = get_config_value(
        "documents", "scanner_extensions", default=[".md", ".mdx", ".rst", ".txt"]
    )
    scanner_ignore: list[str] = get_config_value("documents", "scanner_ignore", default=[])


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
    max_tokens: int = get_config_value("documents", "link_finder", "max_tokens", default=1000)


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
    max_tokens: int = get_config_value("documents", "drift_detector", "max_tokens", default=1500)
    default_drift_score: float = get_config_value(
        "documents", "drift_detector", "default_drift_score", default=0.5
    )
