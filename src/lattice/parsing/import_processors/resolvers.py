from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


def safe_decode_text(node: Node) -> str | None:
    if node.text:
        return node.text.decode("utf-8")
    return None


def walk_tree(node: Node, target_types: set[str]) -> list[Node]:
    results = []
    stack = [node]

    while stack:
        current = stack.pop()
        if current.type in target_types:
            results.append(current)
        stack.extend(reversed(current.children))

    return results


def resolve_python_module(module_name: str, project_name: str, repo_path: Path) -> str:
    if not module_name:
        return module_name

    top_level = module_name.split(".")[0]

    if (repo_path / top_level).is_dir() or (repo_path / f"{top_level}.py").is_file():
        return f"{project_name}.{module_name}"

    return module_name


def resolve_relative_import(
    relative_node: Node,
    module_qn: str,
    project_name: str,
) -> str:
    module_parts = module_qn.split(".")[1:]
    dots = 0
    module_name = ""

    text = safe_decode_text(relative_node)
    if text:
        while dots < len(text) and text[dots] == ".":
            dots += 1
        module_name = text[dots:]

    if dots > 0:
        target_parts = module_parts[:-(dots)]
    else:
        target_parts = module_parts[:]

    if module_name:
        target_parts.extend(module_name.split("."))

    return f"{project_name}.{'.'.join(target_parts)}" if target_parts else project_name


def resolve_js_module_path(import_path: str, module_qn: str) -> str:
    if not import_path.startswith("."):
        return import_path.replace("/", ".")

    current_parts = module_qn.split(".")[:-1]
    import_parts = import_path.split("/")

    for part in import_parts:
        if part == ".":
            continue
        elif part == "..":
            if current_parts:
                current_parts.pop()
        elif part:
            current_parts.append(part)

    return ".".join(current_parts)
