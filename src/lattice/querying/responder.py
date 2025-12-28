import logging

from lattice.infrastructure.llm import BaseLLMProvider, get_llm_provider
from lattice.prompts import get_prompt
from lattice.querying.reranker import SearchResult
from lattice.shared.config import QueryConfig, get_settings
from lattice.shared.exceptions import QueryError

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates natural language responses using configurable LLM providers."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        settings = get_settings()
        self.temperature = settings.llm_temperature

        self._llm_provider: BaseLLMProvider = get_llm_provider(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=self.temperature,
        )

        logger.info(
            f"Initialized ResponseGenerator with "
            f"{self._llm_provider.config.provider}/{self._llm_provider.config.model}"
        )

    async def generate_response(
        self,
        question: str,
        results: list[SearchResult],
        max_context_results: int | None = None,
    ) -> str:
        if max_context_results is None:
            max_context_results = QueryConfig.max_context_results

        try:
            logger.debug(f"Generating response for question: {question}")
            context = self._build_context(results[:max_context_results])

            system_prompt = get_prompt("query", "system")
            response_prompt = get_prompt("query", "response", question=question, context=context)

            answer = await self._llm_provider.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": response_prompt},
                ],
                max_tokens=get_settings().query.max_response_tokens,
            )

            logger.debug(f"Generated response length: {len(answer)}")
            return answer

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise QueryError("Failed to generate response", cause=e)

    async def generate_explanation(
        self,
        code: str,
        language: str,
        question: str | None = None,
    ) -> str:
        try:
            logger.debug(f"Generating explanation for {language} code")

            system_prompt = get_prompt("query", "system")

            if question:
                prompt = get_prompt(
                    "query",
                    "explanation_with_question",
                    language=language,
                    question=question,
                    code=code,
                )
            else:
                prompt = get_prompt("query", "explanation", language=language, code=code)

            answer = await self._llm_provider.complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=get_settings().query.max_explanation_tokens,
            )

            logger.debug(f"Generated explanation length: {len(answer)}")
            return answer

        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            raise QueryError("Failed to generate explanation", cause=e)

    def _build_context(self, results: list[SearchResult]) -> str:
        max_content_length = QueryConfig.max_content_length
        context_parts = []

        for i, result in enumerate(results, 1):
            parts = [f"### Result {i}"]
            parts.append(f"**File**: {result.file_path}")
            parts.append(f"**Entity**: {result.entity_name} ({result.entity_type})")

            if result.start_line:
                parts.append(f"**Lines**: {result.start_line}-{result.end_line}")

            if result.summary:
                parts.append(f"**Summary**: {result.summary}")

            if result.content:
                content = result.content[:max_content_length]
                if len(result.content) > max_content_length:
                    content += "\n... (truncated)"
                parts.append(f"**Code**:\n```\n{content}\n```")

            context_parts.append("\n".join(parts))

        return "\n\n".join(context_parts)
