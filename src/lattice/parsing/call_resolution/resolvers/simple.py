"""Simple name and same-module call resolution strategies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lattice.shared.cache import FunctionRegistry
    from lattice.parsing.import_processor import ImportProcessor

logger = logging.getLogger(__name__)


def resolve_same_module_call(
    call_name: str,
    module_qn: str,
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    simple_name = call_name.split(".")[0].split("(")[0]
    local_qn = f"{module_qn}.{simple_name}"
    entity_type = function_registry.get(local_qn)
    if entity_type:
        logger.debug(f"Same-module resolved: {call_name} -> {local_qn}")
        return (entity_type, local_qn)
    return None


def resolve_by_simple_name(
    call_name: str,
    module_qn: str,
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    simple_name = call_name.split(".")[-1].split("(")[0]
    matches = function_registry.find_by_simple_name(simple_name)
    if not matches:
        return None
    matches.sort(key=lambda qn: calculate_distance(qn, module_qn))
    best_qn = matches[0]
    entity_type = function_registry.get(best_qn)
    if entity_type:
        logger.debug(f"Fallback resolved: {call_name} -> {best_qn}")
        return (entity_type, best_qn)
    return None


def calculate_distance(candidate_qn: str, caller_module_qn: str) -> int:
    caller_parts = caller_module_qn.split(".")
    candidate_parts = candidate_qn.split(".")
    common_prefix = 0
    for i in range(min(len(caller_parts), len(candidate_parts))):
        if caller_parts[i] == candidate_parts[i]:
            common_prefix += 1
        else:
            break
    distance = (len(caller_parts) - common_prefix) + (len(candidate_parts) - common_prefix)
    if candidate_qn.startswith(caller_module_qn + "."):
        distance -= 2
    return distance


def resolve_class_name(
    class_name: str,
    module_qn: str,
    function_registry: FunctionRegistry,
    import_processor: ImportProcessor,
) -> str | None:
    local_qn = f"{module_qn}.{class_name}"
    if function_registry.get(local_qn) == "Class":
        return local_qn
    import_map = import_processor.get_import_mapping(module_qn)
    if import_map and class_name in import_map:
        return import_map[class_name]
    matches = function_registry.find_by_simple_name(class_name)
    for match in matches:
        if function_registry.get(match) == "Class":
            return match
    return None
