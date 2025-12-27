from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.config import get_settings
from lattice.core.cache import ASTCache
from lattice.parsing.language_config import get_config_for_file

if TYPE_CHECKING:
    from lattice.embeddings.indexer import VectorIndexer
    from lattice.graph.builder import GraphBuilder
    from lattice.parsing.parser import CodeParser

logger = logging.getLogger(__name__)


def _import_watchdog():
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        return FileSystemEventHandler, Observer
    except ImportError:
        raise ImportError(
            "Real-time updates require the 'watchdog' package. "
            "Install with: pip install watchdog"
        )


class FileChangeHandler:
    def __init__(
        self,
        repo_path: Path,
        on_file_changed: Callable[[Path], None],
        on_file_deleted: Callable[[Path], None],
    ):
        self.repo_path = repo_path
        self.on_file_changed = on_file_changed
        self.on_file_deleted = on_file_deleted

        settings = get_settings()
        self.ignore_patterns = set(settings.ignore_patterns)
        self.supported_extensions = set(settings.supported_extensions)

        self._pending_changes: dict[Path, str] = {}
        self._debounce_delay = 0.5

    def _is_relevant(self, path: Path) -> bool:
        if path.suffix.lower() not in self.supported_extensions:
            return False

        try:
            relative = path.relative_to(self.repo_path)
            for part in relative.parts:
                if part in self.ignore_patterns:
                    return False
        except ValueError:
            return False

        return True

    def handle_event(self, event_type: str, src_path: str) -> None:
        path = Path(src_path)

        if path.is_dir() or not self._is_relevant(path):
            return

        logger.info(f"File {event_type}: {path}")

        if event_type in ("created", "modified"):
            self.on_file_changed(path)
        elif event_type == "deleted":
            self.on_file_deleted(path)


class FileWatcher:
    """Watches a repository and incrementally updates graph on file changes.

    Real-Time Graph Update Strategy (from reference repo insights):
    1. Delete all old data from the graph for the changed file
    2. Clear the specific in-memory state for the file
    3. Re-parse the file if it was modified or created
    4. Re-process all function calls across the entire codebase
       (This fixes the "island" problem - changes reflect in all relations)
    5. Flush all collected changes to the database

    Note: The CALLS relationship recalculation is critical for accuracy
    because when a file changes, other files' call references to it
    may become valid or invalid.
    """

    def __init__(
        self,
        repo_path: Path,
        graph_builder: GraphBuilder,
        vector_indexer: VectorIndexer,
        parser: CodeParser,
        ast_cache: ASTCache | None = None,
        recalculate_calls: bool = True,
    ):
        self.repo_path = repo_path.resolve()
        self.graph_builder = graph_builder
        self.vector_indexer = vector_indexer
        self.parser = parser
        self.ast_cache = ast_cache or ASTCache()
        self.recalculate_calls = recalculate_calls

        self._observer = None
        self._running = False
        self._update_queue: asyncio.Queue[tuple[str, Path]] = asyncio.Queue()
        self._update_task = None

        # Track pending changes for batch processing
        self._pending_changes: set[Path] = set()
        self._batch_delay = 1.0  # Seconds to wait before processing batch

        self.files_updated = 0
        self.files_deleted = 0
        self.calls_recalculated = 0
        self.errors = 0

    async def start(self) -> None:
        if self._running:
            logger.warning("Watcher already running")
            return

        FileSystemEventHandler, Observer = _import_watchdog()

        class WatchdogHandler(FileSystemEventHandler):
            def __init__(handler_self, change_handler: FileChangeHandler):
                super().__init__()
                handler_self.change_handler = change_handler

            def on_created(handler_self, event):
                if not event.is_directory:
                    handler_self.change_handler.handle_event("created", event.src_path)

            def on_modified(handler_self, event):
                if not event.is_directory:
                    handler_self.change_handler.handle_event("modified", event.src_path)

            def on_deleted(handler_self, event):
                if not event.is_directory:
                    handler_self.change_handler.handle_event("deleted", event.src_path)

        change_handler = FileChangeHandler(
            repo_path=self.repo_path,
            on_file_changed=lambda p: self._queue_update("changed", p),
            on_file_deleted=lambda p: self._queue_update("deleted", p),
        )

        self._observer = Observer()
        handler = WatchdogHandler(change_handler)
        self._observer.schedule(handler, str(self.repo_path), recursive=True)
        self._observer.start()
        self._running = True

        self._update_task = asyncio.create_task(self._process_updates())

        logger.info(f"Started watching: {self.repo_path}")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None

        logger.info(f"Stopped watching: {self.repo_path}")
        logger.info(f"Stats: {self.files_updated} updated, {self.files_deleted} deleted, {self.errors} errors")

    async def run_forever(self) -> None:
        await self.start()
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    def _queue_update(self, action: str, path: Path) -> None:
        try:
            self._update_queue.put_nowait((action, path))
        except asyncio.QueueFull:
            logger.warning(f"Update queue full, dropping: {path}")

    async def _process_updates(self) -> None:
        while self._running:
            try:
                action, path = await asyncio.wait_for(
                    self._update_queue.get(),
                    timeout=1.0,
                )

                if action == "changed":
                    await self._handle_file_changed(path)
                elif action == "deleted":
                    await self._handle_file_deleted(path)

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing update: {e}")
                self.errors += 1

    async def _handle_file_changed(self, file_path: Path) -> None:
        """Handle a file change event.

        This follows the reference repo's update strategy:
        1. Delete old entities for this file from the graph
        2. Clear in-memory state (AST cache)
        3. Re-parse the file
        4. Rebuild graph entities
        5. Optionally recalculate CALLS relationships across the codebase
        """
        logger.info(f"Processing file change: {file_path}")

        try:
            if not file_path.exists():
                logger.debug(f"File no longer exists: {file_path}")
                return

            lang_config = get_config_for_file(file_path)
            if not lang_config:
                logger.debug(f"Unsupported file type: {file_path}")
                return

            from lattice.core.types import Language
            from lattice.parsing.models import FileInfo

            content = file_path.read_text(encoding="utf-8", errors="replace")
            import hashlib

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

            parsed_file = await asyncio.to_thread(
                self.parser.parse_file, file_info
            )

            if parsed_file:
                relative_path = str(file_path.relative_to(self.repo_path))

                # Step 1: Delete old entities from graph
                await self.graph_builder.delete_file_entities(relative_path)

                # Step 2: Clear from AST cache
                if file_path in self.ast_cache:
                    del self.ast_cache[file_path]

                # Step 3 & 4: Rebuild graph with new parsed content
                await self.graph_builder.build_from_parsed_file(parsed_file)

                # Step 5: Update vector embeddings
                await self.vector_indexer.index_file(
                    parsed_file,
                    project_name=self.repo_path.name,
                )

                # Cache the new AST for future call resolution
                if hasattr(parsed_file, "_tree") and parsed_file._tree:
                    self.ast_cache[file_path] = (
                        parsed_file._tree.root_node,
                        lang_config.name,
                    )

                self.files_updated += 1
                logger.info(f"Updated: {file_path}")

                # Step 6: Recalculate CALLS relationships if enabled
                # This is critical for accuracy - when a file changes,
                # other files' call references to it may become valid or invalid
                if self.recalculate_calls:
                    await self._recalculate_calls_for_file(file_path)

        except Exception as e:
            logger.error(f"Failed to update {file_path}: {e}")
            self.errors += 1

    async def _recalculate_calls_for_file(self, changed_file: Path) -> None:
        """Recalculate CALLS relationships affected by a file change.

        When a file changes (function renamed, added, or removed),
        other files that call or are called by this file need their
        CALLS relationships updated.

        This prevents "island" problems where graph relationships
        become stale.
        """
        try:
            relative_path = str(changed_file.relative_to(self.repo_path))

            # Delete existing CALLS relationships involving this file
            await self.graph_builder.delete_calls_for_file(relative_path)

            # Rebuild CALLS relationships for this file
            # The graph builder's build_from_parsed_file should have
            # already registered the functions, so we just need to
            # resolve the calls
            await self.graph_builder.rebuild_calls_for_file(relative_path)

            self.calls_recalculated += 1
            logger.debug(f"Recalculated CALLS for: {relative_path}")

        except AttributeError:
            # Graph builder may not have these methods yet
            logger.debug("CALLS recalculation not supported by graph builder")
        except Exception as e:
            logger.warning(f"Failed to recalculate CALLS for {changed_file}: {e}")

    async def _handle_file_deleted(self, file_path: Path) -> None:
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


async def start_watcher(
    repo_path: str | Path,
    graph_builder: GraphBuilder,
    vector_indexer: VectorIndexer,
    parser: CodeParser,
) -> FileWatcher:
    watcher = FileWatcher(
        repo_path=Path(repo_path),
        graph_builder=graph_builder,
        vector_indexer=vector_indexer,
        parser=parser,
    )
    await watcher.start()
    return watcher
