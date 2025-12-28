from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lattice.parsing.type_inference.models import (
    InferredType,
    TypeInferenceContext,
    TypeSource,
    VariableTypeMap,
)
from lattice.parsing.type_inference.utils import get_node_text

if TYPE_CHECKING:
    from tree_sitter import Node


def resolve_type_name(
    type_name: str,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> str | None:
    if context.module_qn in import_mapping:
        imports = import_mapping[context.module_qn]
        if type_name in imports:
            return imports[type_name]

    local_qn = f"{context.module_qn}.{type_name}"
    if function_registry and local_qn in function_registry:
        return local_qn

    if function_registry:
        if hasattr(function_registry, "find_by_simple_name"):
            matches = function_registry.find_by_simple_name(type_name)
            if len(matches) == 1:
                return matches[0]

    return None


def infer_type_from_name(
    name: str,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
    function_registry: Any,
) -> InferredType | None:
    if "_" in name:
        parts = name.split("_")
        class_name = "".join(p.capitalize() for p in parts)
    else:
        class_name = name.capitalize()

    resolved = resolve_type_name(class_name, context, import_mapping, function_registry)
    if resolved:
        return InferredType(
            type_name=class_name,
            qualified_name=resolved,
            source=TypeSource.INFERRED,
            confidence=0.5,
        )

    return None


def get_receiver_type(
    object_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
    import_mapping: dict[str, dict[str, str]],
) -> str | None:
    if object_node.type == "identifier":
        var_name = get_node_text(object_node)
        if var_name:
            if var_name in type_map:
                inferred = type_map[var_name]
                return inferred.qualified_name or inferred.type_name

            if var_name == "self" and context.class_qn:
                return context.class_qn

            if context.module_qn in import_mapping:
                imports = import_mapping[context.module_qn]
                if var_name in imports:
                    return imports[var_name]

    elif object_node.type == "attribute":
        return resolve_attribute_type(object_node, type_map, context)

    return None


def resolve_attribute_type(
    attr_node: Node,
    type_map: VariableTypeMap,
    context: TypeInferenceContext,
) -> str | None:
    object_node = attr_node.child_by_field_name("object")
    attr_name_node = attr_node.child_by_field_name("attribute")

    if not object_node or not attr_name_node:
        return None

    attr_name = get_node_text(attr_name_node)
    if not attr_name:
        return None

    if object_node.type == "identifier":
        obj_name = get_node_text(object_node)
        if obj_name == "self":
            attr_type = type_map.get_instance_attr(attr_name)
            if attr_type:
                return attr_type.qualified_name or attr_type.type_name

    return None
