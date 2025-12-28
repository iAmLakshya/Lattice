from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from lattice.shared.types import Language


@dataclass
class LanguageConfig:
    name: str
    display_name: str
    file_extensions: list[str]

    function_node_types: list[str] = field(default_factory=list)
    class_node_types: list[str] = field(default_factory=list)
    method_node_types: list[str] = field(default_factory=list)
    call_node_types: list[str] = field(default_factory=list)
    import_node_types: list[str] = field(default_factory=list)
    module_node_types: list[str] = field(default_factory=list)
    comment_node_types: list[str] = field(default_factory=list)
    string_node_types: list[str] = field(default_factory=list)

    function_query: str | None = None
    class_query: str | None = None
    import_query: str | None = None
    call_query: str | None = None

    package_indicators: list[str] = field(default_factory=list)
    ignore_patterns: list[str] = field(default_factory=list)

    def matches_extension(self, extension: str) -> bool:
        ext = extension if extension.startswith(".") else f".{extension}"
        return ext.lower() in [e.lower() for e in self.file_extensions]


@dataclass
class FQNConfig:
    scope_node_types: set[str]
    function_node_types: set[str]
    class_node_types: set[str]
    get_name: Callable | None = None
    file_to_module_parts: Callable[[Path, Path], list[str]] | None = None


def _build_language_configs() -> dict[str, LanguageConfig]:
    from lattice.parsing.configs import (
        CPP_CONFIG,
        GO_CONFIG,
        JAVA_CONFIG,
        JAVASCRIPT_CONFIG,
        JSX_CONFIG,
        PYTHON_CONFIG,
        RUST_CONFIG,
        TSX_CONFIG,
        TYPESCRIPT_CONFIG,
    )

    return {
        "python": PYTHON_CONFIG,
        "javascript": JAVASCRIPT_CONFIG,
        "jsx": JSX_CONFIG,
        "typescript": TYPESCRIPT_CONFIG,
        "tsx": TSX_CONFIG,
        "rust": RUST_CONFIG,
        "java": JAVA_CONFIG,
        "go": GO_CONFIG,
        "cpp": CPP_CONFIG,
    }


def _build_extension_map(configs: dict[str, LanguageConfig]) -> dict[str, LanguageConfig]:
    ext_map: dict[str, LanguageConfig] = {}
    for config in configs.values():
        for ext in config.file_extensions:
            ext_map[ext.lower()] = config
    return ext_map


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = _build_language_configs()
_EXTENSION_MAP: dict[str, LanguageConfig] = _build_extension_map(LANGUAGE_CONFIGS)


def get_language_config(extension_or_name: str) -> LanguageConfig | None:
    if extension_or_name in LANGUAGE_CONFIGS:
        return LANGUAGE_CONFIGS[extension_or_name]
    ext = extension_or_name if extension_or_name.startswith(".") else f".{extension_or_name}"
    return _EXTENSION_MAP.get(ext.lower())


def get_config_for_file(file_path: Path) -> LanguageConfig | None:
    return get_language_config(file_path.suffix)


def get_supported_extensions() -> list[str]:
    return list(_EXTENSION_MAP.keys())


def get_supported_languages() -> list[str]:
    return list(LANGUAGE_CONFIGS.keys())


def language_enum_to_config(language: Language) -> LanguageConfig | None:
    name_map = {
        Language.PYTHON: "python",
        Language.JAVASCRIPT: "javascript",
        Language.TYPESCRIPT: "typescript",
        Language.JSX: "jsx",
        Language.TSX: "tsx",
    }
    lang_name = name_map.get(language)
    return LANGUAGE_CONFIGS.get(lang_name) if lang_name else None
