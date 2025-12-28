from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.parsing.type_inference.js_ts_inference import JsTsTypeInference
from lattice.parsing.type_inference.python_traversal import PythonTraversal
from lattice.parsing.type_inference.type_resolver import TypeResolver
from lattice.shared.cache import ASTCache, FunctionRegistry

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)


class TypeInferenceEngine:
    def __init__(
        self,
        function_registry: FunctionRegistry | None = None,
        import_mapping: dict[str, dict[str, str]] | None = None,
        ast_cache: ASTCache | None = None,
        module_qn_to_file_path: dict[str, Path] | None = None,
        simple_name_lookup: dict[str, set[str]] | None = None,
    ):
        self.function_registry = function_registry or FunctionRegistry()
        self.import_mapping = import_mapping or {}
        self.ast_cache = ast_cache or ASTCache()
        self.module_qn_to_file_path = module_qn_to_file_path or {}
        self.simple_name_lookup = simple_name_lookup or {}

        self._type_resolver = TypeResolver(
            function_registry=self.function_registry,
            import_mapping=self.import_mapping,
            ast_cache=self.ast_cache,
            module_qn_to_file_path=self.module_qn_to_file_path,
            simple_name_lookup=self.simple_name_lookup,
        )
        self._python_traversal = PythonTraversal(type_resolver=self._type_resolver)
        self._js_ts_inference = JsTsTypeInference(type_resolver=self._type_resolver)

    def build_local_variable_type_map(
        self,
        caller_node: Node,
        module_qn: str,
        language: str,
    ) -> dict[str, str]:
        local_var_types: dict[str, str] = {}
        try:
            if language == "python":
                self._python_traversal.infer_parameter_types(
                    caller_node, local_var_types, module_qn
                )
                self._python_traversal.traverse_single_pass(
                    caller_node, local_var_types, module_qn
                )
            elif language in ("javascript", "typescript", "jsx", "tsx"):
                self._js_ts_inference.infer_types(
                    caller_node, local_var_types, module_qn, language
                )
        except Exception as e:
            logger.debug(f"Failed to build local variable type map: {e}")
        return local_var_types
