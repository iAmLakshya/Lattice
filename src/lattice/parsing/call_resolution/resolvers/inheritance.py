"""Inheritance-based call resolution strategies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lattice.parsing.call_resolution.builtins import (
    KEYWORD_INIT,
    KEYWORD_SUPER,
)

if TYPE_CHECKING:
    from lattice.shared.cache import FunctionRegistry

logger = logging.getLogger(__name__)


def resolve_super_call(
    call_name: str,
    class_context: str | None,
    class_inheritance: dict[str, list[str]],
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    if not class_context:
        logger.debug(f"No class context for super() call: {call_name}")
        return None

    if call_name == KEYWORD_SUPER or call_name == f"{KEYWORD_SUPER}()":
        method_name = KEYWORD_INIT
    elif call_name.startswith(f"{KEYWORD_SUPER}()."):
        method_name = call_name.split(".", 1)[1].split("(")[0]
    elif call_name.startswith(f"{KEYWORD_SUPER}."):
        method_name = call_name.split(".", 1)[1].split("(")[0]
    else:
        return None

    if class_context not in class_inheritance:
        logger.debug(f"No inheritance info for {class_context}")
        return None

    result = resolve_inherited_method(class_context, method_name, class_inheritance, function_registry)
    if result:
        logger.debug(f"Resolved super() call: {call_name} -> {result[1]}")
        return result

    logger.debug(f"Could not resolve super() call: {call_name}")
    return None


def resolve_inherited_method(
    class_qn: str,
    method_name: str,
    class_inheritance: dict[str, list[str]],
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    if class_qn not in class_inheritance:
        return None

    visited = set()
    queue = list(class_inheritance.get(class_qn, []))

    while queue:
        parent_qn = queue.pop(0)
        if parent_qn in visited:
            continue
        visited.add(parent_qn)

        method_qn = f"{parent_qn}.{method_name}"
        entity_type = function_registry.get(method_qn)
        if entity_type:
            return (entity_type, method_qn)

        if parent_qn in class_inheritance:
            for grandparent_qn in class_inheritance[parent_qn]:
                if grandparent_qn not in visited:
                    queue.append(grandparent_qn)
    return None
