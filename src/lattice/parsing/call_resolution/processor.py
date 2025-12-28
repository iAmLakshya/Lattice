"""Call resolution processor for resolving function/method calls."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.parsing.call_resolution.builtins import (
    KEYWORD_SUPER,
    OPERATOR_PREFIX,
    SEPARATOR_COLON,
    SEPARATOR_DOT,
    SEPARATOR_DOUBLE_COLON,
)
from lattice.parsing.call_resolution.extractors import (
    extract_calls_from_node as _extract_calls,
    safe_decode_text,
)
from lattice.parsing.call_resolution.resolvers import (
    resolve_builtin_call,
    resolve_by_simple_name,
    resolve_chained_call,
    resolve_cpp_operator_call,
    resolve_iife,
    resolve_same_module_call,
    resolve_super_call,
    resolve_via_imports,
)

__all__ = ["CallProcessor", "safe_decode_text"]

if TYPE_CHECKING:
    from tree_sitter import Node

    from lattice.shared.cache import FunctionRegistry
    from lattice.parsing.import_processor import ImportProcessor
    from lattice.parsing.type_inference.engine import TypeInferenceEngine

_RE_METHOD_CHAIN = re.compile(r"\)\.")
_RE_FINAL_METHOD = re.compile(r"\.([^.()]+)$")


class CallProcessor:
    """Resolves function and method calls using multiple resolution strategies."""

    def __init__(
        self,
        function_registry: FunctionRegistry,
        import_processor: ImportProcessor,
        type_inference: TypeInferenceEngine,
        class_inheritance: dict[str, list[str]],
        project_name: str,
        repo_path: Path,
    ):
        self.function_registry = function_registry
        self.import_processor = import_processor
        self.type_inference = type_inference
        self.class_inheritance = class_inheritance
        self.project_name = project_name
        self.repo_path = repo_path

    def resolve_call(
        self,
        call_name: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
        class_context: str | None = None,
        language: str = "python",
    ) -> tuple[str, str] | None:
        if not call_name:
            return None

        if result := resolve_iife(call_name, module_qn, language, self.function_registry):
            return result

        if self._is_super_call(call_name):
            return resolve_super_call(
                call_name, class_context, self.class_inheritance, self.function_registry
            )

        if language in ("cpp", "c++") and call_name.startswith(OPERATOR_PREFIX):
            if result := resolve_cpp_operator_call(call_name, module_qn, self.function_registry):
                return result

        if self._has_separator(call_name) and self._is_method_chain(call_name):
            return resolve_chained_call(
                call_name,
                module_qn,
                local_var_types,
                self.class_inheritance,
                self.function_registry,
                self.import_processor,
                self.type_inference,
                _RE_FINAL_METHOD,
            )

        import_result = resolve_via_imports(
            call_name,
            module_qn,
            local_var_types,
            self.class_inheritance,
            self.function_registry,
            self.import_processor,
        )
        if import_result:
            return import_result

        same_module_result = resolve_same_module_call(call_name, module_qn, self.function_registry)
        if same_module_result:
            return same_module_result

        builtin_result = resolve_builtin_call(call_name, language)
        if builtin_result:
            return builtin_result

        return resolve_by_simple_name(call_name, module_qn, self.function_registry)

    def _is_super_call(self, call_name: str) -> bool:
        return (
            call_name == KEYWORD_SUPER
            or call_name.startswith(f"{KEYWORD_SUPER}.")
            or call_name.startswith(f"{KEYWORD_SUPER}()")
        )

    def _has_separator(self, call_name: str) -> bool:
        return (
            SEPARATOR_DOT in call_name
            or SEPARATOR_DOUBLE_COLON in call_name
            or SEPARATOR_COLON in call_name
        )

    def _is_method_chain(self, call_name: str) -> bool:
        if "(" in call_name and ")" in call_name:
            return bool(_RE_METHOD_CHAIN.search(call_name))
        return False

    def extract_calls_from_node(
        self,
        node: Node,
        source: str,
        language: str,
    ) -> list[str]:
        return _extract_calls(node, language)
