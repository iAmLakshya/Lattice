from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lattice.parsing.type_inference.extractors import (
    find_containing_class,
    find_init_method,
)
from lattice.parsing.type_inference.inferrers import infer_type_from_expression
from lattice.parsing.type_inference.models import (
    TypeInferenceContext,
    VariableTypeMap,
)
from lattice.parsing.type_inference.utils import get_node_text

if TYPE_CHECKING:
    from tree_sitter import Node


def infer_instance_attrs_from_init(
    function_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> None:
    class_node = find_containing_class(function_node)
    if not class_node:
        return

    init_node = find_init_method(class_node)
    if not init_node:
        return

    analyze_self_assignments(init_node, type_map, context, import_mapping, function_registry)


def analyze_self_assignments(
    node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> None:
    stack = [node]

    while stack:
        current = stack.pop()

        if current.type == "assignment":
            left = current.child_by_field_name("left")
            right = current.child_by_field_name("right")

            if left and right and left.type == "attribute":
                left_text = get_node_text(left)
                if left_text and left_text.startswith("self."):
                    attr_name = left_text[5:]
                    inferred = infer_type_from_expression(
                        right, context, import_mapping, function_registry
                    )
                    if inferred:
                        type_map.set_instance_attr(attr_name, inferred)

        if current.type not in ("function_definition", "class_definition"):
            stack.extend(reversed(current.children))
