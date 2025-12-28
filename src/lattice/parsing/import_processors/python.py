from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.parsing.import_processors.resolvers import (
    resolve_python_module,
    resolve_relative_import,
    safe_decode_text,
    walk_tree,
)

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)


def parse_python_imports(
    root_node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
    project_name: str,
    repo_path: Path,
) -> None:
    for node in walk_tree(root_node, {"import_statement", "import_from_statement"}):
        if node.type == "import_statement":
            _handle_import_statement(node, module_qn, import_mapping, project_name, repo_path)
        elif node.type == "import_from_statement":
            _handle_import_from_statement(node, module_qn, import_mapping, project_name, repo_path)


def _handle_import_statement(
    node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
    project_name: str,
    repo_path: Path,
) -> None:
    for child in node.children:
        if child.type == "dotted_name":
            module_name = safe_decode_text(child)
            if module_name:
                local_name = module_name.split(".")[0]
                full_name = resolve_python_module(module_name, project_name, repo_path)
                import_mapping[module_qn][local_name] = full_name
                logger.debug(f"Import: {local_name} -> {full_name}")

        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            if name_node and alias_node:
                module_name = safe_decode_text(name_node)
                alias = safe_decode_text(alias_node)
                if module_name and alias:
                    full_name = resolve_python_module(module_name, project_name, repo_path)
                    import_mapping[module_qn][alias] = full_name
                    logger.debug(f"Aliased import: {alias} -> {full_name}")


def _handle_import_from_statement(
    node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
    project_name: str,
    repo_path: Path,
) -> None:
    module_name_node = node.child_by_field_name("module_name")
    if module_name_node is None:
        for child in node.children:
            if child.type == "dotted_name":
                module_name_node = child
                break
            elif child.type == "relative_import":
                module_name_node = child
                break

    if not module_name_node:
        return

    if module_name_node.type == "relative_import":
        base_module = resolve_relative_import(module_name_node, module_qn, project_name)
    else:
        module_text = safe_decode_text(module_name_node)
        base_module = (
            resolve_python_module(module_text, project_name, repo_path) if module_text else ""
        )

    if not base_module:
        return

    is_wildcard = any(child.type == "wildcard_import" for child in node.children)

    if is_wildcard:
        wildcard_key = f"*{base_module}"
        import_mapping[module_qn][wildcard_key] = base_module
        logger.debug(f"Wildcard import: * -> {base_module}")
        return

    _process_from_import_names(node, module_name_node, module_qn, import_mapping, base_module)


def _process_from_import_names(
    node: Node,
    module_name_node: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
    base_module: str,
) -> None:
    for child in node.children:
        if child.type == "dotted_name" and child != module_name_node:
            name = safe_decode_text(child)
            if name:
                full_name = f"{base_module}.{name}"
                import_mapping[module_qn][name] = full_name
                logger.debug(f"From import: {name} -> {full_name}")

        elif child.type == "aliased_import":
            _handle_aliased_from_import(child, module_qn, import_mapping, base_module)


def _handle_aliased_from_import(
    child: Node,
    module_qn: str,
    import_mapping: dict[str, dict[str, str]],
    base_module: str,
) -> None:
    name_node = child.child_by_field_name("name")
    if name_node is None:
        for subchild in child.children:
            if subchild.type in ("identifier", "dotted_name"):
                name_node = subchild
                break

    alias_node = child.child_by_field_name("alias")
    if alias_node is None:
        found_as = False
        for subchild in child.children:
            if subchild.type == "as":
                found_as = True
            elif found_as and subchild.type == "identifier":
                alias_node = subchild
                break

    if name_node:
        name = safe_decode_text(name_node)
        alias = safe_decode_text(alias_node) if alias_node else name
        if name and alias:
            full_name = f"{base_module}.{name}"
            import_mapping[module_qn][alias] = full_name
            logger.debug(f"From aliased import: {alias} -> {full_name}")
