import logging

from lattice.indexing.context import PipelineContext
from lattice.parsing.api import FileScanner
from lattice.shared.exceptions import IndexingError
from lattice.shared.types import PipelineStage as PipelineStageEnum

logger = logging.getLogger(__name__)


class ScanStage:
    name: str = "scan"

    async def execute(self, ctx: PipelineContext) -> None:
        ctx.tracker.set_stage(PipelineStageEnum.SCANNING, message="Scanning repository...")
        logger.info(f"Scanning repository: {ctx.repo_path}")

        try:
            scanner = FileScanner(ctx.repo_path)
            ctx.scanned_files = scanner.scan_all()

            ctx.tracker.update_stats(files_scanned=len(ctx.scanned_files))
            ctx.tracker.update_stage(
                len(ctx.scanned_files),
                len(ctx.scanned_files),
                f"Found {len(ctx.scanned_files)} files",
            )
            logger.info(f"Scanned {len(ctx.scanned_files)} files")

        except Exception as e:
            logger.error(f"File scanning failed: {e}", exc_info=True)
            raise IndexingError(f"File scanning failed: {e}", stage="scanning", cause=e)
