import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from lattice.infrastructure.llm import BaseLLMProvider
from lattice.prompts import get_prompt
from lattice.querying.query_planner.models import (
    ExtractedEntity,
    QueryIntent,
    QueryPlan,
    QueryRelationship,
    SubQuery,
)
from lattice.querying.query_planner.parsers import (
    build_fallback_plan,
    determine_search_type,
    extract_json,
)
from lattice.shared.exceptions import QueryError

logger = logging.getLogger(__name__)


class QueryPlanner:
    def __init__(self, llm_provider: BaseLLMProvider):
        self._llm_provider = llm_provider

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def plan_query(self, question: str) -> QueryPlan:
        if not question or not question.strip():
            raise QueryError("Question cannot be empty")

        try:
            logger.debug(f"Planning query: {question}")

            analysis_prompt = get_prompt("query", "analysis", question=question)
            system_prompt = get_prompt("query", "planning_system")

            content = await self._llm_provider.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": analysis_prompt},
                ],
                temperature=0.0,
                max_tokens=2000,
            )

            if content:
                content = content.strip()

            analysis = extract_json(content)
            plan = self._build_query_plan(question, analysis)

            logger.debug(
                f"Query plan: intent={plan.primary_intent}, sub_queries={len(plan.sub_queries)}"
            )
            return plan

        except (json.JSONDecodeError, ValueError, KeyError, TypeError, AttributeError) as e:
            logger.debug(f"Query planning parse error ({type(e).__name__}), fallback")
            return build_fallback_plan(question)
        except Exception as e:
            logger.debug(
                f"Unexpected error during query planning ({type(e).__name__}: {e}), "
                "using heuristic fallback"
            )
            return build_fallback_plan(question)

    def _build_query_plan(self, question: str, analysis: dict[str, Any]) -> QueryPlan:
        intent_str = analysis.get("primary_intent", "search_functionality")
        try:
            primary_intent = QueryIntent(intent_str)
        except ValueError:
            primary_intent = QueryIntent.SEARCH_FUNCTIONALITY

        entities = []
        for e in analysis.get("entities", []):
            entities.append(
                ExtractedEntity(
                    name=e.get("name", ""),
                    entity_type=e.get("type"),
                    is_primary=e.get("is_primary", False),
                    context=e.get("context"),
                )
            )

        relationships = []
        for r in analysis.get("relationships", []):
            relationships.append(
                QueryRelationship(
                    source=r.get("source", ""),
                    target=r.get("target", ""),
                    relationship_type=r.get("type", "related_to"),
                )
            )

        multi_hop = analysis.get("multi_hop", {})
        requires_multi_hop = multi_hop.get("required", False)
        max_hops = multi_hop.get("max_hops", 1)

        context_requirements = analysis.get("context_requirements", [])

        sub_queries = []
        for i, sq in enumerate(analysis.get("sub_queries", [])):
            intent_str = sq.get("intent", "search_functionality")
            try:
                sq_intent = QueryIntent(intent_str)
            except ValueError:
                sq_intent = QueryIntent.SEARCH_FUNCTIONALITY

            sq_entities = [e for e in entities if e.name.lower() in sq.get("query", "").lower()]

            sub_queries.append(
                SubQuery(
                    query_text=sq.get("query", question),
                    intent=sq_intent,
                    entities=sq_entities,
                    relationships=[],
                    search_type=sq.get("search_type", "hybrid"),
                    priority=sq.get("priority", i + 1),
                    depends_on=sq.get("depends_on", []),
                )
            )

        if not sub_queries:
            sub_queries.append(
                SubQuery(
                    query_text=question,
                    intent=primary_intent,
                    entities=entities,
                    relationships=relationships,
                    search_type=determine_search_type(primary_intent),
                    priority=1,
                )
            )

        return QueryPlan(
            original_query=question,
            primary_intent=primary_intent,
            sub_queries=sub_queries,
            entities=entities,
            relationships=relationships,
            requires_multi_hop=requires_multi_hop,
            max_hops=max_hops,
            context_requirements=context_requirements,
            reasoning=analysis.get("reasoning", ""),
        )
