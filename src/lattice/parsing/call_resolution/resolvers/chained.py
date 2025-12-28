"""Chained call and special case resolution strategies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lattice.parsing.call_resolution.builtins import (
    CPP_OPERATORS,
    IIFE_ARROW_PREFIX,
    IIFE_FUNC_PREFIX,
    SEPARATOR_DOT,
)
from lattice.parsing.call_resolution.resolvers.inheritance import resolve_inherited_method
from lattice.parsing.call_resolution.resolvers.simple import resolve_class_name

if TYPE_CHECKING:
    from lattice.parsing.import_processor import ImportProcessor
    from lattice.parsing.type_inference.engine import TypeInferenceEngine
    from lattice.shared.cache import FunctionRegistry

logger = logging.getLogger(__name__)


def resolve_iife(
    call_name: str,
    module_qn: str,
    language: str,
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    if language not in ("javascript", "typescript", "jsx", "tsx"):
        return None
    if not call_name:
        return None
    if not (call_name.startswith(IIFE_FUNC_PREFIX) or call_name.startswith(IIFE_ARROW_PREFIX)):
        return None

    iife_qn = f"{module_qn}{SEPARATOR_DOT}{call_name}"
    entity_type = function_registry.get(iife_qn)
    if entity_type:
        logger.debug(f"IIFE resolved: {call_name} -> {iife_qn}")
        return (entity_type, iife_qn)
    return None


def resolve_cpp_operator_call(
    call_name: str,
    module_qn: str,
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    if call_name in CPP_OPERATORS:
        return ("Function", CPP_OPERATORS[call_name])

    matches = function_registry.find_by_simple_name(call_name)
    if matches:
        same_module_ops = [qn for qn in matches if qn.startswith(module_qn) and call_name in qn]
        candidates = same_module_ops or matches
        candidates.sort(key=lambda qn: (len(qn), qn))
        best = candidates[0]
        entity_type = function_registry.get(best)
        if entity_type:
            return (entity_type, best)
    return None


def resolve_chained_call(
    call_name: str,
    module_qn: str,
    local_var_types: dict[str, str] | None,
    class_inheritance: dict[str, list[str]],
    function_registry: FunctionRegistry,
    import_processor: ImportProcessor,
    type_inference: TypeInferenceEngine,
    final_method_pattern,
) -> tuple[str, str] | None:
    match = final_method_pattern.search(call_name)
    if not match:
        return None

    final_method = match.group(1)
    object_expr = call_name[: match.start()]

    object_type = _infer_expression_type(object_expr, module_qn, local_var_types, type_inference)
    if not object_type:
        return None

    resolved_class = resolve_class_name(object_type, module_qn, function_registry, import_processor)
    if not resolved_class:
        resolved_class = object_type

    method_qn = f"{resolved_class}{SEPARATOR_DOT}{final_method}"
    entity_type = function_registry.get(method_qn)
    if entity_type:
        logger.debug(f"Resolved chained call: {call_name} -> {method_qn}")
        return (entity_type, method_qn)

    inherited = resolve_inherited_method(
        resolved_class, final_method, class_inheritance, function_registry
    )
    if inherited:
        logger.debug(f"Resolved chained inherited call: {call_name} -> {inherited[1]}")
        return inherited
    return None


def _infer_expression_type(
    expr: str,
    module_qn: str,
    local_var_types: dict[str, str] | None,
    type_inference: TypeInferenceEngine,
) -> str | None:
    if local_var_types and expr in local_var_types:
        return local_var_types[expr]
    if "(" in expr:
        if type_inference:
            return type_inference._infer_method_call_return_type(expr, module_qn, local_var_types)
    return None
