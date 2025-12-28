import logging

from lattice.infrastructure.llm import BaseLLMProvider
from lattice.prompts import get_prompt
from lattice.querying.context import EnrichedContext, format_context_for_llm
from lattice.querying.query_planner import QueryIntent, QueryPlan
from lattice.querying.ranking import RankedResult

logger = logging.getLogger(__name__)


class ResponseBuilder:
    def __init__(self, llm_provider: BaseLLMProvider):
        self._llm_provider = llm_provider

    async def generate_response(
        self,
        question: str,
        plan: QueryPlan,
        results: list[RankedResult],
        context: EnrichedContext,
    ) -> str:
        context_text = format_context_for_llm(context)

        system_prompt = self._get_system_prompt(plan.primary_intent)
        user_prompt = self._build_user_prompt(question, plan, context_text)

        response = await self._llm_provider.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
        )

        return response.strip()

    def _get_system_prompt(self, intent: QueryIntent) -> str:
        base_prompt = get_prompt("query", "enhanced_system")

        intent_prompt_map = {
            QueryIntent.FIND_CALLERS: "intent_find_callers",
            QueryIntent.FIND_CALLEES: "intent_find_callees",
            QueryIntent.FIND_CALL_CHAIN: "intent_find_call_chain",
            QueryIntent.FIND_HIERARCHY: "intent_find_hierarchy",
            QueryIntent.EXPLAIN_IMPLEMENTATION: "intent_explain_implementation",
            QueryIntent.EXPLAIN_DATA_FLOW: "intent_explain_data_flow",
            QueryIntent.SEARCH_FUNCTIONALITY: "intent_search_functionality",
        }

        prompt_name = intent_prompt_map.get(intent)
        if prompt_name:
            return base_prompt + get_prompt("query", prompt_name)
        return base_prompt

    def _build_user_prompt(
        self,
        question: str,
        plan: QueryPlan,
        context_text: str,
    ) -> str:
        entities_section = ""
        if plan.entities:
            entities_str = ", ".join(f"`{e.name}`" for e in plan.entities)
            entities_section = f"- **Key Entities**: {entities_str}"

        multi_hop_section = ""
        if plan.requires_multi_hop:
            multi_hop_section = (
                f"- **Reasoning Depth**: Multi-hop analysis (up to {plan.max_hops} hops)"
            )

        reasoning_section = ""
        if plan.reasoning:
            reasoning_section = f"- **Search Strategy**: {plan.reasoning}"

        return get_prompt(
            "query",
            "enhanced_user",
            question=question,
            intent=plan.primary_intent.value,
            entities_section=entities_section,
            multi_hop_section=multi_hop_section,
            reasoning_section=reasoning_section,
            context_text=context_text,
        )
