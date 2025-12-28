from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.parsing.api import FileInfo, get_config_for_file
from lattice.shared.cache import ASTCache
from lattice.shared.types import Language

if TYPE_CHECKING:
    from lattice.infrastructure.memgraph import GraphBuilder
    from lattice.infrastructure.qdrant import VectorIndexer
    from lattice.parsing.api import CodeParser

logger = logging.getLogger(__name__)


class FileUpdateHandler:
    def __init__(
        self,
        repo_path: Path,
        graph_builder: GraphBuilder,
        vector_indexer: VectorIndexer,
        parser: CodeParser,
        ast_cache: ASTCache,
        recalculate_calls: bool = True,
    ):
        self.repo_path = repo_path
        self.graph_builder = graph_builder
        self.vector_indexer = vector_indexer
        self.parser = parser
        self.ast_cache = ast_cache
        self.recalculate_calls = recalculate_calls

        self.files_updated = 0
        self.files_deleted = 0
        self.calls_recalculated = 0
        self.errors = 0

    async def handle_file_changed(self, file_path: Path) -> None:
        logger.info(f"Processing file change: {file_path}")

        try:
            if not file_path.exists():
                logger.debug(f"File no longer exists: {file_path}")
                return

            lang_config = get_config_for_file(file_path)
            if not lang_config:
                logger.debug(f"Unsupported file type: {file_path}")
                return

            content = file_path.read_text(encoding="utf-8", errors="replace")
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            lang_map = {
                "python": Language.PYTHON,
                "javascript": Language.JAVASCRIPT,
                "typescript": Language.TYPESCRIPT,
                "jsx": Language.JSX,
                "tsx": Language.TSX,
            }
            language = lang_map.get(lang_config.name, Language.PYTHON)
            file_info = FileInfo(
                path=file_path,
                relative_path=str(file_path.relative_to(self.repo_path)),
                language=language,
                content_hash=content_hash,
                size_bytes=len(content.encode()),
                line_count=content.count("\n") + 1,
            )

            parsed_file = await asyncio.to_thread(self.parser.parse_file, file_info)

            if parsed_file:
                relative_path = str(file_path.relative_to(self.repo_path))

                await self.graph_builder.delete_file_entities(relative_path)

                if file_path in self.ast_cache:
                    del self.ast_cache[file_path]

                await self.graph_builder.build_from_parsed_file(parsed_file)

                await self.vector_indexer.index_file(
                    parsed_file,
                    project_name=self.repo_path.name,
                )

                if hasattr(parsed_file, "_tree") and parsed_file._tree:
                    self.ast_cache[file_path] = (
                        parsed_file._tree.root_node,
                        lang_config.name,
                    )

                self.files_updated += 1
                logger.info(f"Updated: {file_path}")

                if self.recalculate_calls:
                    await self._recalculate_calls_for_file(file_path)

        except Exception as e:
            logger.error(f"Failed to update {file_path}: {e}")
            self.errors += 1

    async def _recalculate_calls_for_file(self, changed_file: Path) -> None:
        try:
            relative_path = str(changed_file.relative_to(self.repo_path))

            await self.graph_builder.delete_calls_for_file(relative_path)
            await self.graph_builder.rebuild_calls_for_file(relative_path)

            self.calls_recalculated += 1
            logger.debug(f"Recalculated CALLS for: {relative_path}")

        except AttributeError:
            logger.debug("CALLS recalculation not supported by graph builder")
        except Exception as e:
            logger.warning(f"Failed to recalculate CALLS for {changed_file}: {e}")

    async def handle_file_deleted(self, file_path: Path) -> None:
        logger.info(f"Processing file deletion: {file_path}")

        try:
            relative_path = str(file_path.relative_to(self.repo_path))

            await self.graph_builder.delete_file_entities(relative_path)
            await self.vector_indexer.delete_file(relative_path)

            if file_path in self.ast_cache:
                del self.ast_cache[file_path]

            self.files_deleted += 1
            logger.info(f"Deleted: {file_path}")

        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            self.errors += 1
