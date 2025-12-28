from dataclasses import dataclass, field
from enum import Enum


class QueryIntent(Enum):
    FIND_CALLERS = "find_callers"
    FIND_CALLEES = "find_callees"
    FIND_CALL_CHAIN = "find_call_chain"
    FIND_HIERARCHY = "find_hierarchy"
    FIND_IMPLEMENTATIONS = "find_implementations"
    FIND_USAGES = "find_usages"
    FIND_DEPENDENCIES = "find_dependencies"
    FIND_DEPENDENTS = "find_dependents"

    LOCATE_ENTITY = "locate_entity"
    LOCATE_FILE = "locate_file"

    EXPLAIN_IMPLEMENTATION = "explain_implementation"
    EXPLAIN_RELATIONSHIP = "explain_relationship"
    EXPLAIN_DATA_FLOW = "explain_data_flow"
    EXPLAIN_ARCHITECTURE = "explain_architecture"

    FIND_SIMILAR = "find_similar"
    SEARCH_FUNCTIONALITY = "search_functionality"
    SEARCH_PATTERN = "search_pattern"


@dataclass
class ExtractedEntity:
    name: str
    entity_type: str | None = None
    is_primary: bool = False
    context: str | None = None


@dataclass
class QueryRelationship:
    source: str
    target: str
    relationship_type: str


@dataclass
class SubQuery:
    query_text: str
    intent: QueryIntent
    entities: list[ExtractedEntity]
    relationships: list[QueryRelationship]
    search_type: str
    priority: int = 1
    depends_on: list[int] = field(default_factory=list)


@dataclass
class QueryPlan:
    original_query: str
    primary_intent: QueryIntent
    sub_queries: list[SubQuery]
    entities: list[ExtractedEntity]
    relationships: list[QueryRelationship]
    requires_multi_hop: bool = False
    max_hops: int = 1
    context_requirements: list[str] = field(default_factory=list)
    reasoning: str = ""
