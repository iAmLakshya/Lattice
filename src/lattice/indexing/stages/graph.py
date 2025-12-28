import asyncio
import logging

from lattice.indexing.context import PipelineContext
from lattice.infrastructure.memgraph import BatchGraphBuilder, GraphBuilder, GraphStatistics
from lattice.shared.exceptions import IndexingError
from lattice.shared.types import PipelineStage as PipelineStageEnum

logger = logging.getLogger(__name__)


class GraphBuildStage:
    name: str = "graph"

    async def execute(self, ctx: PipelineContext) -> None:
        ctx.tracker.set_stage(
            PipelineStageEnum.GRAPH_BUILDING,
            total=len(ctx.parsed_files),
            message="Building knowledge graph (batched)...",
        )
        batch_size = ctx.max_concurrent_api * 100
        logger.info(f"Building knowledge graph with batched operations (batch_size={batch_size})")

        try:
            legacy_builder = GraphBuilder(
                ctx.memgraph,
                call_processor=ctx.call_processor,
                project_name=ctx.project_name,
            )
            await legacy_builder.create_project(ctx.project_name, str(ctx.repo_path))

            async def check_file_update(parsed_file):
                file_path = str(parsed_file.file_info.path)
                async with ctx.graph_semaphore:
                    needs_update = await legacy_builder.file_needs_update(
                        file_path,
                        parsed_file.file_info.content_hash,
                    )
                return (parsed_file, file_path, needs_update)

            check_tasks = [check_file_update(pf) for pf in ctx.parsed_files]
            check_results = await asyncio.gather(*check_tasks, return_exceptions=True)

            files_to_update = []
            for result in check_results:
                if isinstance(result, Exception):
                    logger.warning(f"Failed to check file update status: {result}")
                    continue
                parsed_file, file_path, needs_update = result
                if ctx.force:
                    needs_update = True
                ctx.file_update_status[file_path] = needs_update
                if needs_update:
                    files_to_update.append(parsed_file)

            if ctx.force:
                logger.info(f"Force mode: updating all {len(files_to_update)} files")
            else:
                logger.info(f"{len(files_to_update)} files need graph updates")

            for parsed_file in files_to_update:
                file_path = str(parsed_file.file_info.path)
                try:
                    await legacy_builder.delete_file_entities(file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete old entities for {file_path}: {e}")

            async with BatchGraphBuilder(
                ctx.memgraph,
                call_processor=ctx.call_processor,
                project_name=ctx.project_name,
                batch_size=batch_size,
            ) as batch_builder:
                completed = len(ctx.parsed_files) - len(files_to_update)
                files_updated = 0

                for parsed_file in files_to_update:
                    try:
                        await batch_builder.add_parsed_file(parsed_file)
                        files_updated += 1
                        completed += 1
                        ctx.tracker.update_stage(
                            completed,
                            message=f"Graph: {parsed_file.file_info.relative_path} (Buffered)",
                        )
                    except Exception as e:
                        completed += 1
                        logger.warning(
                            f"Failed to add {parsed_file.file_info.relative_path} to graph: {e}"
                        )
                        ctx.tracker.update_stage(
                            completed,
                            message=f"Graph: {parsed_file.file_info.relative_path} (Failed)",
                        )

                logger.info(f"Flushing {files_updated} files to graph database...")

            graph_stats = GraphStatistics(legacy_builder.client)
            stats = await graph_stats.get_entity_counts()
            total_nodes = sum(stats.values())
            ctx.tracker.update_stats(graph_nodes_created=total_nodes)

            logger.info(
                f"Graph building complete: {files_updated} files updated, "
                f"{total_nodes} total nodes (batched mode)"
            )

        except Exception as e:
            logger.error(f"Graph building failed: {e}", exc_info=True)
            raise IndexingError(f"Graph building failed: {e}", stage="graph_building", cause=e)
