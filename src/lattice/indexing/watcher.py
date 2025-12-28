from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.indexing.handlers import FileUpdateHandler
from lattice.shared.cache import ASTCache
from lattice.shared.config import WatcherConfig, get_settings

if TYPE_CHECKING:
    from lattice.infrastructure.memgraph import GraphBuilder
    from lattice.infrastructure.qdrant import VectorIndexer
    from lattice.parsing.api import CodeParser

logger = logging.getLogger(__name__)


def _import_watchdog():
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        return FileSystemEventHandler, Observer
    except ImportError:
        raise ImportError(
            "Real-time updates require the 'watchdog' package. Install with: pip install watchdog"
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
        self._debounce_delay = WatcherConfig.debounce_delay

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
    def __init__(
        self,
        repo_path: Path,
        graph_builder: GraphBuilder,
        vector_indexer: VectorIndexer,
        parser: CodeParser,
        ast_cache: ASTCache,
        recalculate_calls: bool = True,
    ):
        self.repo_path = repo_path.resolve()
        self._handler = FileUpdateHandler(
            repo_path=self.repo_path,
            graph_builder=graph_builder,
            vector_indexer=vector_indexer,
            parser=parser,
            ast_cache=ast_cache,
            recalculate_calls=recalculate_calls,
        )

        self._observer = None
        self._running = False
        self._update_queue: asyncio.Queue[tuple[str, Path]] = asyncio.Queue()
        self._update_task = None
        self._pending_changes: set[Path] = set()

    @property
    def files_updated(self) -> int:
        return self._handler.files_updated

    @property
    def files_deleted(self) -> int:
        return self._handler.files_deleted

    @property
    def calls_recalculated(self) -> int:
        return self._handler.calls_recalculated

    @property
    def errors(self) -> int:
        return self._handler.errors

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
        logger.info(
            f"Stats: {self.files_updated} updated, {self.files_deleted} deleted, {self.errors} errors"
        )

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
                    await self._handler.handle_file_changed(path)
                elif action == "deleted":
                    await self._handler.handle_file_deleted(path)

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing update: {e}")


async def start_watcher(
    repo_path: str | Path,
    graph_builder: GraphBuilder,
    vector_indexer: VectorIndexer,
    parser: CodeParser,
    ast_cache: ASTCache,
) -> FileWatcher:
    watcher = FileWatcher(
        repo_path=Path(repo_path),
        graph_builder=graph_builder,
        vector_indexer=vector_indexer,
        parser=parser,
        ast_cache=ast_cache,
    )
    await watcher.start()
    return watcher
