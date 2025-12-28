"""Call extraction utilities for extracting function/method calls from AST nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


def safe_decode_text(node: Node) -> str | None:
    if node.text:
        return node.text.decode("utf-8")
    return None


def extract_calls_from_node(
    node: Node,
    language: str,
) -> list[str]:
    calls = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if _is_call_node(current, language):
            call_name = _get_call_name(current, language)
            if call_name:
                calls.add(call_name)
        stack.extend(reversed(current.children))
    return list(calls)


def _is_call_node(node: Node, language: str) -> bool:
    if language == "python":
        return node.type == "call"
    elif language in ("javascript", "typescript", "jsx", "tsx"):
        return node.type == "call_expression"
    elif language == "java":
        return node.type == "method_invocation"
    else:
        return node.type in ("call", "call_expression")


def _get_call_name(node: Node, language: str) -> str | None:
    func_node = None
    if language == "python":
        if node.children:
            func_node = node.children[0]
    else:
        func_node = node.child_by_field_name("function")
    if func_node:
        text = safe_decode_text(func_node)
        if text:
            return text
    return None
