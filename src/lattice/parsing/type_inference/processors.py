from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lattice.parsing.type_inference.extractors import extract_variable_name
from lattice.parsing.type_inference.inferrers import (
    infer_iterable_element_type,
    infer_method_return_type,
    infer_simple_type,
    infer_type_from_expression,
)
from lattice.parsing.type_inference.instance_attrs import (
    infer_instance_attrs_from_init,
)
from lattice.parsing.type_inference.models import (
    InferredType,
    TypeInferenceContext,
    TypeSource,
    VariableTypeMap,
)
from lattice.parsing.type_inference.resolvers import infer_type_from_name, resolve_type_name
from lattice.parsing.type_inference.utils import get_node_text

if TYPE_CHECKING:
    from tree_sitter import Node

__all__ = [
    "infer_instance_attrs_from_init",
    "infer_loop_variable_types",
    "infer_parameter_types",
    "process_complex_assignment",
    "process_simple_assignment",
]


def infer_parameter_types(
    function_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> None:
    params_node = function_node.child_by_field_name("parameters")
    if not params_node:
        return

    for param in params_node.children:
        if param.type == "identifier":
            param_name = get_node_text(param)
            if param_name:
                if param_name in ("self", "cls"):
                    continue

                inferred = infer_type_from_name(
                    param_name, context, import_mapping, function_registry
                )
                if inferred:
                    type_map.set_type(param_name, inferred)

        elif param.type == "typed_parameter":
            name_node = param.child_by_field_name("name")
            type_node = param.child_by_field_name("type")

            if name_node and type_node:
                param_name = get_node_text(name_node)
                type_name = get_node_text(type_node)

                if param_name and type_name:
                    resolved_qn = resolve_type_name(
                        type_name, context, import_mapping, function_registry
                    )
                    type_map.set_type(
                        param_name,
                        InferredType(
                            type_name=type_name,
                            qualified_name=resolved_qn,
                            source=TypeSource.ANNOTATION,
                        ),
                    )

        elif param.type == "default_parameter":
            name_node = param.child_by_field_name("name")
            value_node = param.child_by_field_name("value")

            if name_node and value_node:
                param_name = get_node_text(name_node)
                if param_name:
                    inferred = infer_type_from_expression(
                        value_node, context, import_mapping, function_registry
                    )
                    if inferred:
                        type_map.set_type(param_name, inferred)


def process_simple_assignment(
    assignment: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> None:
    left = assignment.child_by_field_name("left")
    right = assignment.child_by_field_name("right")

    if not left or not right:
        return

    var_name = extract_variable_name(left)
    if not var_name:
        return

    if var_name in type_map:
        return

    inferred = infer_simple_type(right, context, import_mapping, function_registry)
    if inferred:
        type_map.set_type(var_name, inferred)


def process_complex_assignment(
    assignment: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
    return_type_cache: dict[str, str | None],
    in_progress: set[str],
) -> None:
    left = assignment.child_by_field_name("left")
    right = assignment.child_by_field_name("right")

    if not left or not right:
        return

    var_name = extract_variable_name(left)
    if not var_name:
        return

    if var_name in type_map:
        return

    if right.type == "call":
        inferred = infer_method_return_type(
            right,
            type_map,
            context,
            import_mapping,
            function_registry,
            return_type_cache,
            in_progress,
        )
        if inferred:
            type_map.set_type(var_name, inferred)


def infer_loop_variable_types(
    function_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> None:
    stack = [function_node]

    while stack:
        current = stack.pop()

        if current.type == "for_statement":
            left = current.child_by_field_name("left")
            right = current.child_by_field_name("right")

            if left and right:
                var_name = extract_variable_name(left)
                if var_name and var_name not in type_map:
                    elem_type = infer_iterable_element_type(
                        right, context, import_mapping, function_registry
                    )
                    if elem_type:
                        type_map.set_type(var_name, elem_type)

        if current.type not in ("function_definition", "class_definition"):
            stack.extend(reversed(current.children))
