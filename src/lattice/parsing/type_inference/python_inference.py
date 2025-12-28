from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from lattice.parsing.type_inference.extractors import collect_assignments
from lattice.parsing.type_inference.models import (
    TypeInferenceContext,
    VariableTypeMap,
)
from lattice.parsing.type_inference.processors import (
    infer_instance_attrs_from_init,
    infer_loop_variable_types,
    infer_parameter_types,
    process_complex_assignment,
    process_simple_assignment,
)

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)


class PythonTypeInference:
    def __init__(
        self,
        function_registry: Any = None,
        import_mapping: dict[str, dict[str, str]] | None = None,
    ):
        self.function_registry = function_registry
        self.import_mapping = import_mapping or {}
        self._return_type_cache: dict[str, str | None] = {}
        self._in_progress: set[str] = set()

    def infer_local_types(
        self,
        function_node: Node,
        context: TypeInferenceContext,
    ) -> VariableTypeMap:
        type_map = VariableTypeMap()

        try:
            infer_parameter_types(
                function_node,
                type_map,
                context,
                self.import_mapping,
                self.function_registry,
            )

            assignments = collect_assignments(function_node)

            for assignment in assignments:
                process_simple_assignment(
                    assignment,
                    type_map,
                    context,
                    self.import_mapping,
                    self.function_registry,
                )

            for assignment in assignments:
                process_complex_assignment(
                    assignment,
                    type_map,
                    context,
                    self.import_mapping,
                    self.function_registry,
                    self._return_type_cache,
                    self._in_progress,
                )

            infer_loop_variable_types(
                function_node,
                type_map,
                context,
                self.import_mapping,
                self.function_registry,
            )

            if context.class_name:
                infer_instance_attrs_from_init(
                    function_node,
                    type_map,
                    context,
                    self.import_mapping,
                    self.function_registry,
                )

        except Exception as e:
            logger.debug(f"Error inferring types: {e}")

        return type_map
