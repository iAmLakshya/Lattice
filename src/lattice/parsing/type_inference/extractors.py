from __future__ import annotations

from typing import TYPE_CHECKING

from lattice.parsing.type_inference.utils import get_node_text

if TYPE_CHECKING:
    from tree_sitter import Node


def collect_assignments(node: Node) -> list[Node]:
    assignments = []
    stack = [node]

    while stack:
        current = stack.pop()
        if current.type == "assignment":
            assignments.append(current)
        if current.type not in ("function_definition", "class_definition"):
            stack.extend(reversed(current.children))

    return assignments


def extract_variable_name(node: Node) -> str | None:
    if node.type == "identifier":
        return get_node_text(node)
    return None


def find_containing_class(node: Node) -> Node | None:
    current = node.parent
    while current:
        if current.type == "class_definition":
            return current
        current = current.parent
    return None


def find_init_method(class_node: Node) -> Node | None:
    body = class_node.child_by_field_name("body")
    if not body:
        return None

    for child in body.children:
        if child.type == "function_definition":
            name_node = child.child_by_field_name("name")
            if name_node:
                name = get_node_text(name_node)
                if name == "__init__":
                    return child

    return None
