import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lattice.indexing.context import PipelineContext
from lattice.parsing.api import CallProcessor, ParsedFile, TypeInferenceEngine
from lattice.shared.cache import ASTCache
from lattice.shared.types import PipelineStage as PipelineStageEnum

logger = logging.getLogger(__name__)


class ParseStage:
    name: str = "parse"

    async def execute(self, ctx: PipelineContext) -> None:
        ctx.tracker.set_stage(
            PipelineStageEnum.PARSING,
            total=len(ctx.scanned_files),
            message=f"Parsing source files (using {ctx.max_workers} workers)...",
        )
        logger.info(f"Parsing {len(ctx.scanned_files)} files with {ctx.max_workers} workers")

        loop = asyncio.get_event_loop()
        parsed_results: list[tuple] = []

        def parse_file_sync(file_info):
            try:
                parsed = ctx.parser.parse_file(file_info)
                return (file_info, parsed, None)
            except Exception as e:
                return (file_info, None, e)

        with ThreadPoolExecutor(max_workers=ctx.max_workers) as executor:
            futures = [
                loop.run_in_executor(executor, parse_file_sync, file_info)
                for file_info in ctx.scanned_files
            ]

            completed = 0
            for coro in asyncio.as_completed(futures):
                result = await coro
                parsed_results.append(result)
                completed += 1
                ctx.tracker.update_stage(
                    completed,
                    message=f"Parsed {completed}/{len(ctx.scanned_files)} files",
                )

        total_entities = 0
        for file_info, parsed, error in parsed_results:
            if error:
                logger.warning(
                    f"Failed to parse {file_info.relative_path}: {error}",
                    exc_info=True,
                )
                continue

            if parsed:
                ctx.parsed_files.append(parsed)
                total_entities += len(parsed.all_entities)

                module_qn = self._file_to_module_qn(ctx.project_name, file_info.relative_path)
                self._register_entities(ctx, parsed, module_qn)

                ast_cache = getattr(ctx.parser, "_ast_cache", None)
                if ctx.import_processor and ast_cache:
                    cached = ast_cache.get(file_info.path)
                    if cached:
                        root_node, lang = cached
                        ctx.import_processor.parse_imports(
                            root_node, module_qn, file_info.language.value
                        )

        if ctx.function_registry and ctx.import_processor and ctx.inheritance_tracker:
            type_inference = TypeInferenceEngine(
                function_registry=ctx.function_registry,
                import_mapping=ctx.import_processor.import_mapping,
                ast_cache=getattr(ctx.parser, "_ast_cache", None) or ASTCache(),
                module_qn_to_file_path={},
                simple_name_lookup={},
            )
            ctx.call_processor = CallProcessor(
                function_registry=ctx.function_registry,
                import_processor=ctx.import_processor,
                type_inference=type_inference,
                class_inheritance=ctx.inheritance_tracker.class_inheritance,
                project_name=ctx.project_name,
                repo_path=ctx.repo_path,
            )

        ctx.tracker.update_stats(
            files_parsed=len(ctx.parsed_files),
            entities_found=total_entities,
        )
        logger.info(f"Parsed {len(ctx.parsed_files)} files, found {total_entities} entities")

    def _file_to_module_qn(self, project_name: str, relative_path: str) -> str:
        path = Path(relative_path)
        parts = list(path.with_suffix("").parts)

        if parts and parts[-1] == "__init__":
            parts = parts[:-1]

        return f"{project_name}.{'.'.join(parts)}" if parts else project_name

    def _register_entities(
        self,
        ctx: PipelineContext,
        parsed: ParsedFile,
        module_qn: str,
    ) -> None:
        for entity in parsed.all_entities:
            if entity.qualified_name.startswith(module_qn):
                qn = entity.qualified_name
            else:
                qn = f"{module_qn}.{entity.qualified_name}"

            entity_type = entity.type.value.capitalize()
            ctx.function_registry.register(qn, entity_type)

            if entity.type.value == "class" and ctx.inheritance_tracker:
                ctx.inheritance_tracker.register_class(qn, entity.base_classes, module_qn)
