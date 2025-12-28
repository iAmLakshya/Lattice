import asyncio
import logging

from lattice.shared.types import PipelineStage as PipelineStageEnum
from lattice.infrastructure.qdrant.indexer import VectorIndexer
from lattice.indexing.context import PipelineContext

logger = logging.getLogger(__name__)


class EmbedStage:
    name: str = "embed"

    async def execute(self, ctx: PipelineContext) -> None:
        files_to_embed = [
            pf
            for pf in ctx.parsed_files
            if ctx.file_update_status.get(str(pf.file_info.path), True)
        ]

        ctx.tracker.set_stage(
            PipelineStageEnum.EMBEDDING,
            total=len(ctx.parsed_files),
            message=f"Generating embeddings ({ctx.max_concurrent_api} concurrent)...",
        )
        logger.info(
            f"Generating embeddings for {len(files_to_embed)} files "
            f"with {ctx.max_concurrent_api} concurrent operations"
        )

        indexer = VectorIndexer(ctx.qdrant, ctx.embedder)

        total_chunks = 0
        files_embedded = 0
        completed = len(ctx.parsed_files) - len(files_to_embed)

        async def embed_file_with_retry(parsed_file, max_retries=3):
            for attempt in range(max_retries):
                try:
                    async with ctx.api_semaphore:
                        chunks = await indexer.index_file(
                            parsed_file,
                            force=True,
                            project_name=ctx.project_name,
                        )
                        return (parsed_file, chunks, None)
                except Exception as e:
                    error_str = str(e).lower()
                    if "rate limit" in error_str or "429" in error_str:
                        wait_time = (attempt + 1) * 2
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    return (parsed_file, 0, e)
            return (parsed_file, 0, Exception("Rate limit exceeded after retries"))

        batch_size = min(3, ctx.max_concurrent_api)
        for i in range(0, len(files_to_embed), batch_size):
            batch = files_to_embed[i : i + batch_size]
            batch_coros = [embed_file_with_retry(pf) for pf in batch]
            batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)

            for result in batch_results:
                completed += 1
                if isinstance(result, Exception):
                    logger.warning(f"Embedding exception: {result}")
                    ctx.tracker.update_stage(completed)
                    continue

                pf, chunks, error = result
                if error:
                    logger.warning(f"Failed to embed {pf.file_info.relative_path}: {error}")
                    status = "Failed"
                else:
                    total_chunks += chunks
                    files_embedded += 1
                    status = f"Embedded ({chunks} chunks)"

                ctx.tracker.update_stage(
                    completed,
                    message=f"Embedding {pf.file_info.relative_path} - {status}",
                )

        ctx.tracker.update_stats(chunks_embedded=total_chunks)
        logger.info(f"Embedded {files_embedded} files, {total_chunks} total chunks")
