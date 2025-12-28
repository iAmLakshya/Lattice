from dataclasses import dataclass
from typing import Any

from lattice.querying.context import EnrichedContext
from lattice.querying.graph_reasoning import GraphContext
from lattice.querying.query_planner import QueryPlan
from lattice.querying.ranking import RankedResult


@dataclass
class QueryResult:
    answer: str
    sources: list[RankedResult]
    query_plan: QueryPlan
    context: EnrichedContext
    graph_context: GraphContext
    execution_stats: dict[str, Any]
