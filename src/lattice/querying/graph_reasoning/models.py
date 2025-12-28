from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lattice.shared.config.loader import QueryReasoningConfig

MAX_TRAVERSAL_DEPTH = QueryReasoningConfig.max_traversal_depth
MAX_RESULTS_PER_QUERY = QueryReasoningConfig.max_results_per_query
MAX_PATH_LENGTH = QueryReasoningConfig.max_path_length
MAX_RELATED_ENTITIES = QueryReasoningConfig.max_related_entities


class TraversalDirection(Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


@dataclass
class GraphNode:
    node_type: str
    name: str
    qualified_name: str
    file_path: str
    signature: str | None = None
    docstring: str | None = None
    summary: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    is_async: bool = False
    parent_class: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphPath:
    nodes: list[GraphNode]
    relationships: list[str]
    total_length: int
    path_type: str


@dataclass
class GraphContext:
    primary_entities: list[GraphNode]
    callers: list[GraphNode]
    callees: list[GraphNode]
    parent_classes: list[GraphNode]
    child_classes: list[GraphNode]
    methods: list[GraphNode]
    containing_class: GraphNode | None
    file_context: list[GraphNode]
    dependencies: list[GraphNode]
    dependents: list[GraphNode]
    call_chains: list[GraphPath]
    inheritance_chains: list[GraphPath]
