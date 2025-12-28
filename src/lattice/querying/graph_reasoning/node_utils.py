from typing import Any

from lattice.querying.graph_reasoning.models import GraphNode


def result_to_node(result: dict[str, Any]) -> GraphNode:
    return GraphNode(
        node_type=result.get("node_type", "Unknown"),
        name=result.get("name", ""),
        qualified_name=result.get("qualified_name", ""),
        file_path=result.get("file_path", ""),
        signature=result.get("signature"),
        docstring=result.get("docstring"),
        summary=result.get("summary"),
        start_line=result.get("start_line"),
        end_line=result.get("end_line"),
        is_async=result.get("is_async", False),
        parent_class=result.get("parent_class"),
        metadata={"depth": result.get("depth")} if "depth" in result else {},
    )


def dict_to_node(d: dict[str, Any]) -> GraphNode:
    return GraphNode(
        node_type=d.get("node_type", "Unknown"),
        name=d.get("name", ""),
        qualified_name=d.get("qualified_name", ""),
        file_path=d.get("file_path", ""),
        signature=d.get("signature"),
        docstring=d.get("docstring"),
        summary=d.get("summary"),
        start_line=d.get("start_line"),
        end_line=d.get("end_line"),
        is_async=d.get("is_async", False),
        parent_class=d.get("parent_class"),
    )
