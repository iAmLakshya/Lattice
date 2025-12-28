from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.shared.cache import ASTCache, FunctionRegistry

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)

_RE_METHOD_CHAIN = re.compile(r"\)\.[^)]*$")
_RE_FINAL_METHOD = re.compile(r"\.([^.()]+)$")


def safe_decode_text(node: Node) -> str | None:
    if node.text:
        return node.text.decode("utf-8")
    return None


class TypeResolver:
    def __init__(
        self,
        function_registry: FunctionRegistry,
        import_mapping: dict[str, dict[str, str]],
        ast_cache: ASTCache,
        module_qn_to_file_path: dict[str, Path],
        simple_name_lookup: dict[str, set[str]],
    ):
        self.function_registry = function_registry
        self.import_mapping = import_mapping
        self.ast_cache = ast_cache
        self.module_qn_to_file_path = module_qn_to_file_path
        self.simple_name_lookup = simple_name_lookup
        self._method_return_type_cache: dict[str, str | None] = {}
        self._type_inference_in_progress: set[str] = set()

    def infer_type_from_parameter_name(self, param_name: str, module_qn: str) -> str | None:
        available_class_names = []

        for qn, entity_type in self.function_registry.all_entries().items():
            if entity_type == "Class" and qn.startswith(module_qn + "."):
                remaining = qn[len(module_qn) + 1 :]
                if "." not in remaining:
                    available_class_names.append(remaining)

        if module_qn in self.import_mapping:
            for local_name, imported_qn in self.import_mapping[module_qn].items():
                if self.function_registry.get(imported_qn) == "Class":
                    available_class_names.append(local_name)

        param_lower = param_name.lower()
        best_match = None
        highest_score = 0

        for class_name in available_class_names:
            class_lower = class_name.lower()
            score = 0
            if param_lower == class_lower:
                score = 100
            elif class_lower.endswith(param_lower) or param_lower.endswith(class_lower):
                score = 90
            elif class_lower in param_lower:
                score = int(80 * (len(class_lower) / len(param_lower)))

            if score > highest_score:
                highest_score = score
                best_match = class_name

        return best_match if highest_score > 50 else None

    def infer_method_call_return_type(
        self,
        method_call: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
    ) -> str | None:
        cache_key = f"{module_qn}:{method_call}"
        if cache_key in self._type_inference_in_progress:
            logger.debug(f"Recursion guard: skipping {method_call}")
            return None

        self._type_inference_in_progress.add(cache_key)
        try:
            if "." in method_call and self._is_method_chain(method_call):
                return self._infer_chained_call_return_type(method_call, module_qn, local_var_types)
            return self._infer_simple_method_return_type(method_call, module_qn, local_var_types)
        finally:
            self._type_inference_in_progress.discard(cache_key)

    def _is_method_chain(self, call_name: str) -> bool:
        if "(" in call_name and ")" in call_name:
            return bool(_RE_METHOD_CHAIN.search(call_name))
        return False

    def _infer_chained_call_return_type(
        self,
        call_name: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
    ) -> str | None:
        match = _RE_FINAL_METHOD.search(call_name)
        if not match:
            return None

        final_method = match.group(1)
        object_expr = call_name[: match.start()]
        object_type = self._infer_object_type_for_chained_call(
            object_expr, module_qn, local_var_types
        )

        if object_type:
            method_qn = f"{object_type}.{final_method}"
            return self._get_method_return_type_from_registry(method_qn)
        return None

    def _infer_object_type_for_chained_call(
        self,
        object_expr: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
    ) -> str | None:
        if "(" not in object_expr and local_var_types and object_expr in local_var_types:
            return local_var_types[object_expr]
        if "(" in object_expr and ")" in object_expr:
            return self.infer_method_call_return_type(object_expr, module_qn, local_var_types)
        return None

    def _infer_simple_method_return_type(
        self,
        method_call: str,
        module_qn: str,
        local_var_types: dict[str, str] | None = None,
    ) -> str | None:
        if "." not in method_call:
            return None

        parts = method_call.split(".")
        if len(parts) < 2:
            return None

        class_name = parts[0]
        method_name = parts[-1].split("(")[0] if "(" in parts[-1] else parts[-1]

        if local_var_types and class_name in local_var_types:
            var_type = local_var_types[class_name]
            method_qn = f"{var_type}.{method_name}"
            return self._get_method_return_type_from_registry(method_qn)

        resolved_class = self.resolve_class_name(class_name, module_qn)
        if resolved_class:
            method_qn = f"{resolved_class}.{method_name}"
            return self._get_method_return_type_from_registry(method_qn)
        return None

    def _get_method_return_type_from_registry(self, method_qn: str) -> str | None:
        if method_qn in self._method_return_type_cache:
            return self._method_return_type_cache[method_qn]
        self._method_return_type_cache[method_qn] = None
        return None

    def resolve_class_name(self, class_name: str, module_qn: str) -> str | None:
        local_qn = f"{module_qn}.{class_name}"
        if local_qn in self.function_registry:
            return local_qn
        if module_qn in self.import_mapping:
            if class_name in self.import_mapping[module_qn]:
                return self.import_mapping[module_qn][class_name]
        if class_name in self.simple_name_lookup:
            matches = self.simple_name_lookup[class_name]
            if len(matches) == 1:
                return next(iter(matches))
        return None
