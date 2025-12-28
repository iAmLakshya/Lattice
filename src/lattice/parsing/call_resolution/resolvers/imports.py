"""Import-based call resolution strategies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lattice.parsing.call_resolution.resolvers.inheritance import resolve_inherited_method

if TYPE_CHECKING:
    from lattice.parsing.import_processor import ImportProcessor
    from lattice.shared.cache import FunctionRegistry

logger = logging.getLogger(__name__)


def resolve_via_imports(
    call_name: str,
    module_qn: str,
    local_var_types: dict[str, str] | None,
    class_inheritance: dict[str, list[str]],
    function_registry: FunctionRegistry,
    import_processor: ImportProcessor,
) -> tuple[str, str] | None:
    import_map = import_processor.get_import_mapping(module_qn)
    if not import_map:
        return None

    if call_name in import_map:
        imported_qn = import_map[call_name]
        entity_type = function_registry.get(imported_qn)
        if entity_type:
            logger.debug(f"Direct import resolved: {call_name} -> {imported_qn}")
            return (entity_type, imported_qn)

    if "." in call_name:
        parts = call_name.split(".")
        if len(parts) >= 2:
            object_name = parts[0]
            method_name = ".".join(parts[1:]).split("(")[0]

            if local_var_types and object_name in local_var_types:
                var_type = local_var_types[object_name]
                class_qn = _resolve_type_to_class(
                    var_type, module_qn, import_map, function_registry
                )
                if class_qn:
                    return _try_resolve_method(
                        class_qn, method_name, class_inheritance, function_registry
                    )

            if object_name in import_map:
                imported_qn = import_map[object_name]
                method_qn = f"{imported_qn}.{method_name}"
                entity_type = function_registry.get(method_qn)
                if entity_type:
                    logger.debug(f"Import method resolved: {call_name} -> {method_qn}")
                    return (entity_type, method_qn)

    for local_name, imported_qn in import_map.items():
        if local_name.startswith("*"):
            wildcard_qn = f"{imported_qn}.{call_name}"
            entity_type = function_registry.get(wildcard_qn)
            if entity_type:
                logger.debug(f"Wildcard import resolved: {call_name} -> {wildcard_qn}")
                return (entity_type, wildcard_qn)
    return None


def _resolve_type_to_class(
    type_name: str,
    module_qn: str,
    import_map: dict[str, str],
    function_registry: FunctionRegistry,
) -> str | None:
    if "." in type_name:
        return type_name
    if type_name in import_map:
        return import_map[type_name]
    local_qn = f"{module_qn}.{type_name}"
    if function_registry.get(local_qn) == "Class":
        return local_qn
    matches = function_registry.find_by_simple_name(type_name)
    for match in matches:
        if function_registry.get(match) == "Class":
            return match
    return None


def _try_resolve_method(
    class_qn: str,
    method_name: str,
    class_inheritance: dict[str, list[str]],
    function_registry: FunctionRegistry,
) -> tuple[str, str] | None:
    method_qn = f"{class_qn}.{method_name}"
    entity_type = function_registry.get(method_qn)
    if entity_type:
        return (entity_type, method_qn)
    return resolve_inherited_method(class_qn, method_name, class_inheritance, function_registry)
