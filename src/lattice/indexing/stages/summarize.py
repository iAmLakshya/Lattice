import asyncio
import logging

from lattice.indexing.context import PipelineContext
from lattice.shared.types import PipelineStage as PipelineStageEnum

logger = logging.getLogger(__name__)


class SummarizeStage:
    name: str = "summarize"

    async def execute(self, ctx: PipelineContext) -> None:
        files_to_summarize = [
            pf
            for pf in ctx.parsed_files
            if ctx.file_update_status.get(str(pf.file_info.path), True)
        ]

        summarize_tasks = []
        for pf in files_to_summarize:
            summarize_tasks.append(("file", pf, None))
            for entity in pf.all_entities:
                if entity.type.value in ("class", "function"):
                    summarize_tasks.append(("entity", pf, entity))

        total_items = len(summarize_tasks)

        if total_items == 0:
            ctx.tracker.set_stage(
                PipelineStageEnum.SUMMARIZING,
                total=1,
                message="All summaries up to date",
            )
            ctx.tracker.update_stage(1, message="No files need summarization")
            logger.info("All summaries up to date")
            return

        ctx.tracker.set_stage(
            PipelineStageEnum.SUMMARIZING,
            total=total_items,
            message=f"Generating AI summaries ({ctx.max_concurrent_api} concurrent)...",
        )
        logger.info(
            f"Generating {total_items} summaries "
            f"(max {ctx.max_concurrent_api} concurrent API calls)"
        )

        summaries_generated = 0
        completed = 0

        async def summarize_item_with_retry(task_type, parsed_file, entity, max_retries=3):
            for attempt in range(max_retries):
                try:
                    async with ctx.api_semaphore:
                        if task_type == "file":
                            summary = await ctx.summarizer.summarize_file(parsed_file)
                            parsed_file.summary = summary
                            return ("file", parsed_file.file_info.relative_path, True)
                        else:
                            summary = await ctx.summarizer.summarize_entity(
                                entity,
                                parsed_file.file_info.relative_path,
                                parsed_file.file_info.language.value,
                            )
                            return ("entity", entity.name, summary is not None)
                except Exception as e:
                    error_str = str(e).lower()
                    if "rate limit" in error_str or "429" in error_str:
                        wait_time = (attempt + 1) * 2
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    if task_type == "file":
                        item_name = parsed_file.file_info.relative_path
                    else:
                        item_name = entity.name
                    logger.warning(f"Failed to summarize {item_name}: {e}")
                    return (task_type, item_name, False)
            item_name = parsed_file.file_info.relative_path if task_type == "file" else entity.name
            logger.warning(f"Failed to summarize {item_name} after {max_retries} retries")
            return (task_type, item_name, False)

        batch_size = min(3, ctx.max_concurrent_api)
        for i in range(0, len(summarize_tasks), batch_size):
            batch = summarize_tasks[i : i + batch_size]
            batch_coros = [summarize_item_with_retry(*task) for task in batch]
            batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)

            for result in batch_results:
                completed += 1
                if isinstance(result, Exception):
                    logger.warning(f"Summarization exception: {result}")
                    continue

                task_type, item_name, success = result
                if success:
                    summaries_generated += 1

                ctx.tracker.update_stage(
                    completed,
                    message=f"Summarized {item_name}",
                )

        ctx.tracker.update_stats(summaries_generated=summaries_generated)
        logger.info(f"Generated {summaries_generated} summaries")
