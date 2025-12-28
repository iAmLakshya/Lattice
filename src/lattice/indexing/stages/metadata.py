import logging
from datetime import datetime

from lattice.shared.config import get_settings
from lattice.shared.types import PipelineStage as PipelineStageEnum
from lattice.infrastructure.postgres.postgres import PostgresClient
from lattice.indexing.context import PipelineContext
from lattice.metadata.api import GenerationProgress, MetadataGenerator, MetadataRepository

logger = logging.getLogger(__name__)


class MetadataStage:
    name: str = "metadata"

    async def execute(self, ctx: PipelineContext) -> None:
        settings = get_settings()

        if not settings.metadata.metadata_enabled:
            logger.info("Metadata generation is disabled in settings")
            return

        ctx.tracker.set_stage(
            PipelineStageEnum.METADATA,
            total=7,
            message="Generating project metadata with AI agent...",
        )
        logger.info(f"Generating metadata for {ctx.project_name}")

        def on_progress(progress: GenerationProgress) -> None:
            completed = len(progress.completed_fields) + len(progress.failed_fields)
            ctx.tracker.update_stage(
                completed,
                message=f"Generating {progress.current_field}...",
            )

        postgres = None
        try:
            postgres = PostgresClient()
            await postgres.connect()

            generator = MetadataGenerator(
                repo_path=ctx.repo_path,
                project_name=ctx.project_name,
                progress_callback=on_progress,
            )

            metadata = await generator.generate_all()
            metadata.indexed_at = datetime.now()

            repository = MetadataRepository(postgres)
            await repository.upsert(metadata)

            completed_count = len(generator._progress.completed_fields)
            failed_count = len(generator._progress.failed_fields)

            ctx.tracker.update_stage(
                7,
                message=f"Metadata generated ({completed_count} fields, {failed_count} failed)",
            )

            logger.info(
                f"Metadata generation complete: "
                f"{completed_count} succeeded, {failed_count} failed"
            )

        except Exception as e:
            logger.error(f"Metadata generation failed: {e}", exc_info=True)
            ctx.tracker.update_stage(7, message="Metadata generation skipped (error)")

        finally:
            if postgres:
                try:
                    await postgres.close()
                except Exception as e:
                    logger.warning(f"Failed to close PostgreSQL connection: {e}")
