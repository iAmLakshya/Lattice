from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lattice.parsing.type_inference.models import (
    InferredType,
    TypeInferenceContext,
    TypeSource,
    VariableTypeMap,
)
from lattice.parsing.type_inference.resolvers import get_receiver_type, resolve_type_name
from lattice.parsing.type_inference.utils import get_node_text

if TYPE_CHECKING:
    from tree_sitter import Node


def infer_simple_type(
    expr_node: Node,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> InferredType | None:
    if expr_node.type == "call":
        func_node = expr_node.child_by_field_name("function")
        if func_node and func_node.type == "identifier":
            func_name = get_node_text(func_node)
            if func_name and func_name[0].isupper():
                resolved_qn = resolve_type_name(
                    func_name, context, import_mapping, function_registry
                )
                return InferredType(
                    type_name=func_name,
                    qualified_name=resolved_qn,
                    source=TypeSource.CONSTRUCTOR,
                )

    elif expr_node.type == "list":
        return InferredType(type_name="list", source=TypeSource.INFERRED)

    elif expr_node.type == "dictionary":
        return InferredType(type_name="dict", source=TypeSource.INFERRED)

    elif expr_node.type == "string":
        return InferredType(type_name="str", source=TypeSource.INFERRED)

    elif expr_node.type in ("integer", "float"):
        type_name = "int" if expr_node.type == "integer" else "float"
        return InferredType(type_name=type_name, source=TypeSource.INFERRED)

    return None


def infer_type_from_expression(
    expr_node: Node,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> InferredType | None:
    simple = infer_simple_type(expr_node, context, import_mapping, function_registry)
    if simple:
        return simple

    return None


def infer_method_return_type(
    call_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
    return_type_cache: dict[str, str | None],
    in_progress: set[str],
) -> InferredType | None:
    func_node = call_node.child_by_field_name("function")
    if not func_node:
        return None

    if func_node.type == "identifier":
        func_name = get_node_text(func_node)
        if func_name and func_name[0].isupper():
            resolved_qn = resolve_type_name(func_name, context, import_mapping, function_registry)
            return InferredType(
                type_name=func_name,
                qualified_name=resolved_qn,
                source=TypeSource.CONSTRUCTOR,
            )
        return None

    if func_node.type == "attribute":
        return infer_attribute_call_type(
            func_node,
            type_map,
            context,
            import_mapping,
            return_type_cache,
            in_progress,
        )

    return None


def infer_attribute_call_type(
    attr_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    return_type_cache: dict[str, str | None],
    in_progress: set[str],
) -> InferredType | None:
    object_node = attr_node.child_by_field_name("object")
    attr_name_node = attr_node.child_by_field_name("attribute")

    if not object_node or not attr_name_node:
        return None

    method_name = get_node_text(attr_name_node)
    if not method_name:
        return None

    receiver_type = get_receiver_type(object_node, type_map, context, import_mapping)
    if not receiver_type:
        return None

    method_qn = f"{receiver_type}.{method_name}"

    if method_qn in in_progress:
        return None

    if method_qn in return_type_cache:
        cached = return_type_cache[method_qn]
        if cached:
            return InferredType(
                type_name=cached.split(".")[-1],
                qualified_name=cached,
                source=TypeSource.METHOD_RETURN,
            )
        return None

    return None


def infer_iterable_element_type(
    iterable_node: Node,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> InferredType | None:
    if iterable_node.type == "list":
        for child in iterable_node.children:
            if child.type == "call":
                elem_type = infer_simple_type(child, context, import_mapping, function_registry)
                if elem_type:
                    elem_type.source = TypeSource.LOOP_VARIABLE
                    return elem_type

    return None
