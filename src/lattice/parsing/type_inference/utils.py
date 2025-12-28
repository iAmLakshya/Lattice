from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


def get_node_text(node: Node) -> str | None:
    if node.text:
        return node.text.decode("utf-8")
    return None
