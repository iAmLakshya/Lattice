import asyncio
import logging
from collections.abc import Callable

from lattice.infrastructure.llm import BaseLLMProvider, get_llm_provider
from lattice.parsing.api import CodeEntity, ParsedFile
from lattice.prompts import get_prompt
from lattice.shared.config import SummarizationConfig, get_settings
from lattice.shared.exceptions import SummarizationError
from lattice.shared.api import LLMProviderProtocol as LLMProvider
from lattice.shared.types import EntityType

logger = logging.getLogger(__name__)


def create_code_summarizer(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_concurrent: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> "CodeSummarizer":
    settings = get_settings()
    final_max_tokens = max_tokens or SummarizationConfig.default_max_tokens
    final_temperature = temperature if temperature is not None else SummarizationConfig.default_temperature
    final_max_concurrent = max_concurrent or settings.max_concurrent_requests

    llm_provider = get_llm_provider(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=final_temperature,
        max_tokens=final_max_tokens,
    )

    return CodeSummarizer(
        llm_provider=llm_provider,
        max_concurrent=final_max_concurrent,
        max_tokens=final_max_tokens,
        temperature=final_temperature,
    )


class CodeSummarizer:
    def __init__(
        self,
        llm_provider: LLMProvider | BaseLLMProvider,
        max_concurrent: int,
        max_tokens: int,
        temperature: float,
    ):
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_concurrent = max_concurrent
        self._llm_provider = llm_provider

        if hasattr(self._llm_provider, "set_concurrency"):
            self._llm_provider.set_concurrency(self.max_concurrent)

        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._summarization_strategies = {
            EntityType.CLASS: self._summarize_class,
            EntityType.FUNCTION: self._summarize_function,
            EntityType.METHOD: self._summarize_function,
        }

        logger.info(f"Initialized CodeSummarizer with {getattr(self._llm_provider, 'config', {})}")

    async def _complete(self, system_message: str, user_message: str) -> str:
        try:
            async with self._semaphore:
                return await self._llm_provider.complete(
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise SummarizationError("Failed to generate summary", cause=e)

    async def summarize_file(self, parsed_file: ParsedFile) -> str:
        logger.debug(f"Summarizing file: {parsed_file.file_info.relative_path}")
        content = parsed_file.content[: SummarizationConfig.file_code_max_chars]
        prompt = get_prompt(
            "summarization",
            "file",
            file_path=parsed_file.file_info.relative_path,
            language=parsed_file.file_info.language.value,
            content=content,
        )
        system_message = get_prompt("summarization", "system")
        return await self._complete(system_message, prompt)

    async def _summarize_function(
        self,
        entity: CodeEntity,
        file_path: str,
        language: str,
    ) -> str:
        logger.debug(f"Summarizing function: {entity.qualified_name}")
        code = entity.code[: SummarizationConfig.function_code_max_chars]
        docstring_section = f"Existing docstring:\n{entity.docstring}" if entity.docstring else ""
        prompt = get_prompt(
            "summarization",
            "function",
            entity_name=entity.name,
            file_path=file_path,
            signature=entity.signature or "",
            code=code,
            language=language,
            docstring_section=docstring_section,
        )
        system_message = get_prompt("summarization", "system")
        return await self._complete(system_message, prompt)

    async def _summarize_class(
        self,
        entity: CodeEntity,
        file_path: str,
        language: str,
    ) -> str:
        logger.debug(f"Summarizing class: {entity.qualified_name}")
        code = entity.code[: SummarizationConfig.class_code_max_chars]
        docstring_section = f"Existing docstring:\n{entity.docstring}" if entity.docstring else ""
        prompt = get_prompt(
            "summarization",
            "class",
            entity_name=entity.name,
            file_path=file_path,
            code=code,
            language=language,
            docstring_section=docstring_section,
        )
        system_message = get_prompt("summarization", "system")
        return await self._complete(system_message, prompt)

    async def summarize_entity(
        self,
        entity: CodeEntity,
        file_path: str,
        language: str,
    ) -> str:
        """Generate a summary for any code entity.

        Args:
            entity: Entity to summarize.
            file_path: Source file path.
            language: Programming language.

        Returns:
            Generated summary.

        Raises:
            SummarizationError: If entity type not supported.
        """
        strategy = self._summarization_strategies.get(entity.type)
        if strategy:
            return await strategy(entity, file_path, language)

        logger.warning(f"No summarization strategy for entity type: {entity.type}")
        return ""

    async def summarize_parsed_file(
        self,
        parsed_file: ParsedFile,
        include_entities: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, str]:
        """Generate summaries for a file and its entities.

        Args:
            parsed_file: Parsed file to summarize.
            include_entities: Whether to summarize individual entities.
            progress_callback: Optional progress callback.

        Returns:
            Dictionary mapping entity names to summaries.
        """
        logger.info(f"Summarizing parsed file: {parsed_file.file_info.relative_path}")
        summaries = {}
        file_path = parsed_file.file_info.relative_path
        language = parsed_file.file_info.language.value

        summaries["__file__"] = await self.summarize_file(parsed_file)

        if include_entities:
            entities = parsed_file.all_entities
            total = len(entities) + 1

            for i, entity in enumerate(entities):
                if entity.type in self._summarization_strategies:
                    try:
                        summary = await self.summarize_entity(entity, file_path, language)
                        summaries[entity.qualified_name] = summary
                    except SummarizationError as e:
                        logger.error(f"Failed to summarize {entity.qualified_name}: {e}")
                        summaries[entity.qualified_name] = ""
                    except Exception as e:
                        logger.error(f"Unexpected error summarizing {entity.qualified_name}: {e}")
                        summaries[entity.qualified_name] = ""

                if progress_callback:
                    progress_callback(i + 2, total)

        return summaries
