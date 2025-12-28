import json
import re
from typing import Any

from lattice.querying.query_planner.models import (
    ExtractedEntity,
    QueryIntent,
    QueryPlan,
    SubQuery,
)

_RE_CODE_BLOCK_START = re.compile(r"^```(?:json)?\s*\n?", re.MULTILINE)
_RE_CODE_BLOCK_END = re.compile(r"\n?```\s*$", re.MULTILINE)
_RE_JSON_OBJECT = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
_RE_CAMEL_CASE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
_RE_SNAKE_CASE = re.compile(r"\b([a-z]+(?:_[a-z]+)+)\b")
_RE_BACKTICK = re.compile(r"`([^`]+)`")


def extract_json(content: str) -> dict[str, Any]:
    if not content:
        raise json.JSONDecodeError("Empty content", "", 0)

    content = content.strip()

    def validate_dict(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise ValueError(
                f"Expected JSON object but got {type(result).__name__}: {str(result)[:50]}..."
            )
        return result

    try:
        return validate_dict(json.loads(content))
    except json.JSONDecodeError:
        pass

    content = _RE_CODE_BLOCK_START.sub("", content)
    content = _RE_CODE_BLOCK_END.sub("", content)
    content = content.strip()

    try:
        return validate_dict(json.loads(content))
    except json.JSONDecodeError:
        pass

    first_brace = content.find("{")
    last_brace = content.rfind("}")

    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = content[first_brace : last_brace + 1]
        try:
            return validate_dict(json.loads(json_str))
        except json.JSONDecodeError:
            pass

    match = _RE_JSON_OBJECT.search(content)
    if match:
        try:
            return validate_dict(json.loads(match.group()))
        except json.JSONDecodeError:
            pass

    preview = content[:100] + "..." if len(content) > 100 else content
    raise json.JSONDecodeError(f"Could not extract JSON from: {preview}", content, 0)


def determine_search_type(intent: QueryIntent) -> str:
    graph_primary = {
        QueryIntent.FIND_CALLERS,
        QueryIntent.FIND_CALLEES,
        QueryIntent.FIND_CALL_CHAIN,
        QueryIntent.FIND_HIERARCHY,
        QueryIntent.FIND_USAGES,
        QueryIntent.FIND_DEPENDENCIES,
        QueryIntent.FIND_DEPENDENTS,
        QueryIntent.LOCATE_ENTITY,
        QueryIntent.LOCATE_FILE,
    }

    vector_primary = {
        QueryIntent.FIND_SIMILAR,
        QueryIntent.SEARCH_FUNCTIONALITY,
        QueryIntent.SEARCH_PATTERN,
    }

    if intent in graph_primary:
        return "graph"
    elif intent in vector_primary:
        return "vector"
    else:
        return "hybrid"


def extract_entities_from_text(question: str) -> list[ExtractedEntity]:
    entities = []
    for match in _RE_CAMEL_CASE.findall(question):
        entities.append(ExtractedEntity(name=match, entity_type="class", is_primary=True))
    for match in _RE_SNAKE_CASE.findall(question):
        entities.append(ExtractedEntity(name=match, entity_type="function", is_primary=True))
    for match in _RE_BACKTICK.findall(question):
        entities.append(ExtractedEntity(name=match, is_primary=True))
    return entities


def detect_intent_from_keywords(question_lower: str) -> tuple[QueryIntent, str]:
    if any(kw in question_lower for kw in ["what calls", "who calls", "callers of"]):
        return QueryIntent.FIND_CALLERS, "graph"
    elif any(kw in question_lower for kw in ["calls what", "what does.*call"]):
        return QueryIntent.FIND_CALLEES, "graph"
    elif any(kw in question_lower for kw in ["call chain", "eventually call", "path from.*to"]):
        return QueryIntent.FIND_CALL_CHAIN, "graph"
    elif any(kw in question_lower for kw in ["extends", "inherits", "subclass", "hierarchy"]):
        return QueryIntent.FIND_HIERARCHY, "graph"
    elif any(
        kw in question_lower for kw in ["how does", "how is.*implemented", "implementation of"]
    ):
        return QueryIntent.EXPLAIN_IMPLEMENTATION, "hybrid"
    elif any(kw in question_lower for kw in ["where is", "find the", "locate"]):
        return QueryIntent.LOCATE_ENTITY, "graph"
    elif any(kw in question_lower for kw in ["similar to", "like"]):
        return QueryIntent.FIND_SIMILAR, "vector"
    else:
        return QueryIntent.SEARCH_FUNCTIONALITY, "hybrid"


def build_fallback_plan(question: str) -> QueryPlan:
    question_lower = question.lower()

    intent, search_type = detect_intent_from_keywords(question_lower)
    entities = extract_entities_from_text(question)

    requires_multi_hop = any(
        kw in question_lower
        for kw in ["eventually", "indirectly", "chain", "path", "through", "via"]
    )

    return QueryPlan(
        original_query=question,
        primary_intent=intent,
        sub_queries=[
            SubQuery(
                query_text=question,
                intent=intent,
                entities=entities,
                relationships=[],
                search_type=search_type,
                priority=1,
            )
        ],
        entities=entities,
        relationships=[],
        requires_multi_hop=requires_multi_hop,
        max_hops=3 if requires_multi_hop else 1,
        context_requirements=(
            ["implementation_details"] if intent == QueryIntent.EXPLAIN_IMPLEMENTATION else []
        ),
        reasoning="Fallback heuristic analysis",
    )
