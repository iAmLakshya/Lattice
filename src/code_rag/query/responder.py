import logging

from code_rag.config import get_settings
from code_rag.core.errors import QueryError
from code_rag.providers import get_llm_provider
from code_rag.providers.base import BaseLLMProvider
from code_rag.query.reranker import SearchResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert code analyst helping developers understand codebases.
Your answers must be accurate, traceable, and actionable.

## Response Requirements

**1. TRACEABILITY** (Critical)
- ALWAYS cite specific source locations: `filename:line_number` or `ClassName.method_name`
- Every factual claim must be backed by evidence from the search results
- If information comes from a summary vs. actual code, distinguish between them

**2. ACCURACY**
- Only make claims supported by the provided search results
- Distinguish between certainty levels: "X definitely calls Y" vs "X appears to call Y based on..."
- If results are incomplete or conflicting, explicitly state this

**3. STRUCTURE**
For implementation questions:
- Start with a direct answer to the question
- Follow with supporting evidence and code references
- End with related information that might be helpful

For "where/find" questions:
- Lead with the location(s)
- Briefly explain what's at each location

**4. CODE SNIPPETS**
- Include relevant code snippets when they clarify the answer
- Keep snippets focused - show the relevant portion, not entire functions
- Add brief annotations if the code's purpose isn't obvious

**5. HANDLING UNCERTAINTY**
- If results don't fully answer the question, say what IS known
- Suggest what additional information would help
- Never fabricate information not in the search results

Format responses in markdown for readability."""

QUERY_PROMPT_TEMPLATE = """Answer the user's question using ONLY the search results provided below.

## User Question
{question}

## Search Results
{context}

## Instructions
1. Synthesize information from the search results to directly answer the question
2. Cite specific files and line numbers for every claim (e.g., `user_service.py:45`)
3. If multiple results are relevant, explain how they relate to each other
4. If the results are insufficient, clearly state what's missing and what you CAN determine
5. Do not make up information - only use what's in the search results above"""

EXPLANATION_WITH_QUESTION_TEMPLATE = """Analyze this {language} code and answer the question.

## Question
{question}

## Code
```{language}
{code}
```

## Instructions
1. Directly answer the question first
2. Reference specific line numbers or code sections
3. Explain the relevant logic, data flow, or control flow
4. Note any edge cases, error handling, or important behaviors
5. If the code interacts with other parts of the system, mention those relationships"""

EXPLANATION_TEMPLATE = """Analyze and explain this {language} code.

## Code
```{language}
{code}
```

## Provide an Explanation That Covers:

1. **Purpose**: What is the primary responsibility of this code? (1-2 sentences)

2. **How It Works**: Walk through the key logic:
   - What are the inputs/parameters?
   - What transformations or operations occur?
   - What is returned or what side effects happen?

3. **Key Details**: Note any important aspects:
   - Error handling or edge cases
   - Performance considerations
   - Dependencies on external systems or libraries

4. **Usage**: When/how would a developer use this code?

Keep the explanation concise but complete - suitable for a developer unfamiliar with
this codebase."""

MAX_CONTEXT_RESULTS = 10
MAX_CONTENT_LENGTH = 2000


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
        max_context_results: int = MAX_CONTEXT_RESULTS,
    ) -> str:
        try:
            logger.debug(f"Generating response for question: {question}")
            context = self._build_context(results[:max_context_results])

            answer = await self._llm_provider.complete(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": QUERY_PROMPT_TEMPLATE.format(
                            question=question,
                            context=context,
                        ),
                    },
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

            if question:
                prompt = EXPLANATION_WITH_QUESTION_TEMPLATE.format(
                    language=language,
                    question=question,
                    code=code,
                )
            else:
                prompt = EXPLANATION_TEMPLATE.format(
                    language=language,
                    code=code,
                )

            answer = await self._llm_provider.complete(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
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
                content = result.content[:MAX_CONTENT_LENGTH]
                if len(result.content) > MAX_CONTENT_LENGTH:
                    content += "\n... (truncated)"
                parts.append(f"**Code**:\n```\n{content}\n```")

            context_parts.append("\n".join(parts))

        return "\n\n".join(context_parts)
