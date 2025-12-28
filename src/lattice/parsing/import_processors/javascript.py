from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lattice.parsing.import_processors.resolvers import (
    resolve_js_module_path,
    safe_decode_text,
    walk_tree,
)

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)


def parse_js_ts_imports(
    root_node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    for node in walk_tree(root_node, {"import_statement", "lexical_declaration"}):
        if node.type == "import_statement":
            _handle_import_statement(node, module_qn, import_mapping)
        elif node.type == "lexical_declaration":
            _handle_require(node, module_qn, import_mapping)


def _handle_import_statement(
    node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    source_module = None
    for child in node.children:
        if child.type == "string":
            source_text = safe_decode_text(child)
            if source_text:
                source_module = resolve_js_module_path(source_text.strip("'\""), module_qn)
            break

    if not source_module:
        return

    for child in node.children:
        if child.type == "import_clause":
            _parse_import_clause(child, source_module, module_qn, import_mapping)


def _parse_import_clause(
    clause_node: Node,
    source_module: str,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    for child in clause_node.children:
        if child.type == "identifier":
            name = safe_decode_text(child)
            if name:
                import_mapping[module_qn][name] = f"{source_module}.default"
                logger.debug(f"JS default import: {name} -> {source_module}.default")

        elif child.type == "named_imports":
            _handle_named_imports(child, source_module, module_qn, import_mapping)

        elif child.type == "namespace_import":
            _handle_namespace_import(child, source_module, module_qn, import_mapping)


def _handle_named_imports(
    node: Node,
    source_module: str,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    for subchild in node.children:
        if subchild.type == "import_specifier":
            name_node = subchild.child_by_field_name("name")
            alias_node = subchild.child_by_field_name("alias")
            if name_node:
                name = safe_decode_text(name_node)
                local = safe_decode_text(alias_node) if alias_node else name
                if name and local:
                    import_mapping[module_qn][local] = f"{source_module}.{name}"
                    logger.debug(f"JS named import: {local} -> {source_module}.{name}")


def _handle_namespace_import(
    node: Node,
    source_module: str,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    for subchild in node.children:
        if subchild.type == "identifier":
            name = safe_decode_text(subchild)
            if name:
                import_mapping[module_qn][name] = source_module
                logger.debug(f"JS namespace import: {name} -> {source_module}")
            break


def _handle_require(
    node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")

            if name_node and value_node:
                if name_node.type == "identifier" and value_node.type == "call_expression":
                    _process_require_call(name_node, value_node, module_qn, import_mapping)


def _process_require_call(
    name_node: Node,
    value_node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
) -> None:
    func_node = value_node.child_by_field_name("function")
    args_node = value_node.child_by_field_name("arguments")

    if func_node and safe_decode_text(func_node) == "require" and args_node:
        for arg in args_node.children:
            if arg.type == "string":
                var_name = safe_decode_text(name_node)
                module_path = safe_decode_text(arg)
                if var_name and module_path:
                    module_path = module_path.strip("'\"")
                    resolved = resolve_js_module_path(module_path, module_qn)
                    import_mapping[module_qn][var_name] = resolved
                    logger.debug(f"JS require: {var_name} -> {resolved}")
                break
