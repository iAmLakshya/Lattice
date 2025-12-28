"""Batched graph builder for high-performance graph operations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from lattice.infrastructure.memgraph.batch_operations import (
    flush_all,
    flush_entities,
    flush_relationships,
)
from lattice.infrastructure.memgraph.buffers import EntityBuffer, RelationshipBuffer
from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.infrastructure.memgraph.queries import ProjectQueries
from lattice.parsing.api import CodeEntity, ParsedFile
from lattice.shared.types import EntityType

if TYPE_CHECKING:
    from lattice.parsing.api import CallProcessor

logger = logging.getLogger(__name__)


class BatchGraphBuilder:
    """High-performance graph builder using batched operations."""

    def __init__(
        self,
        client: MemgraphClient,
        call_processor: CallProcessor | None = None,
        project_name: str | None = None,
        project_id: str | None = None,
        batch_size: int = 1000,
    ):
        self.client = client
        self.call_processor = call_processor
        self.project_name = project_name
        self.project_id = project_id if project_id is not None else project_name
        self.batch_size = batch_size

        self._entity_buffer = EntityBuffer()
        self._relationship_buffer = RelationshipBuffer()
        self._stats = {"nodes_created": 0, "relationships_created": 0}

        self._current_file_path: str | None = None
        self._current_module_qn: str | None = None
        self._current_language: str | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.warning(f"Exception during batch building: {exc_val}")
        await self.flush_all()
        return False

    async def create_project(self, name: str, path: str) -> None:
        await self.client.execute(ProjectQueries.CREATE_PROJECT, {"name": name, "path": path})

    def _file_to_module_qn(self, relative_path: str) -> str:
        path = Path(relative_path)
        parts = list(path.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        base = f"{self.project_name}.{'.'.join(parts)}" if parts else self.project_name
        return base if self.project_name else ".".join(parts)

    async def add_parsed_file(self, parsed_file: ParsedFile) -> None:
        file_path = str(parsed_file.file_info.path)
        self._current_file_path = file_path
        self._current_module_qn = self._file_to_module_qn(parsed_file.file_info.relative_path)
        self._current_language = parsed_file.file_info.language.value

        self._entity_buffer.files.append(
            {
                "path": file_path,
                "name": parsed_file.file_info.path.name,
                "language": parsed_file.file_info.language.value,
                "hash": parsed_file.file_info.content_hash,
                "line_count": parsed_file.file_info.line_count,
                "summary": parsed_file.summary,
            }
        )

        for imp in parsed_file.imports:
            self._entity_buffer.imports.append(
                {
                    "name": imp.name,
                    "file_path": file_path,
                    "alias": imp.alias,
                    "source": imp.source,
                    "is_external": imp.is_external,
                    "line_number": imp.line_number,
                }
            )
            self._relationship_buffer.imports.append(
                {
                    "file_path": file_path,
                    "import_name": imp.name,
                }
            )

        for entity in parsed_file.entities:
            await self._add_entity(entity, file_path)

        await self._check_auto_flush()

    async def _add_entity(
        self, entity: CodeEntity, file_path: str, parent_class: str | None = None
    ) -> None:
        if entity.type == EntityType.CLASS:
            await self._add_class(entity, file_path)
        elif entity.type == EntityType.FUNCTION:
            await self._add_function(entity, file_path)
        elif entity.type == EntityType.METHOD:
            await self._add_method(entity, file_path, parent_class)

    def _build_base_properties(self, entity: CodeEntity, file_path: str) -> dict:
        return {
            "qualified_name": entity.qualified_name,
            "name": entity.name,
            "signature": entity.signature,
            "docstring": entity.docstring,
            "summary": None,
            "start_line": entity.start_line,
            "end_line": entity.end_line,
            "file_path": file_path,
            "project_id": self.project_id,
        }

    async def _add_class(self, entity: CodeEntity, file_path: str) -> None:
        self._entity_buffer.classes.append(self._build_base_properties(entity, file_path))
        self._relationship_buffer.defines_class.append(
            {"file_path": file_path, "class_name": entity.qualified_name}
        )
        for base_class in entity.base_classes:
            self._relationship_buffer.extends.append(
                {"child_name": entity.qualified_name, "parent_name": base_class}
            )
        for child in entity.children:
            if child.type == EntityType.METHOD:
                await self._add_method(child, file_path, entity.qualified_name)

    async def _add_function(self, entity: CodeEntity, file_path: str) -> None:
        props = self._build_base_properties(entity, file_path)
        props["is_async"] = entity.is_async
        self._entity_buffer.functions.append(props)
        self._relationship_buffer.defines_function.append(
            {"file_path": file_path, "function_name": entity.qualified_name}
        )
        await self._add_calls_relationships(entity.qualified_name, entity.calls)

    async def _add_method(
        self, entity: CodeEntity, file_path: str, parent_class: str | None
    ) -> None:
        class_name = parent_class or entity.parent_class
        props = self._build_base_properties(entity, file_path)
        props.update(
            {
                "is_async": entity.is_async,
                "is_static": entity.is_static,
                "is_classmethod": entity.is_classmethod,
                "parent_class": class_name,
            }
        )
        self._entity_buffer.methods.append(props)
        if class_name:
            self._relationship_buffer.defines_method.append(
                {"class_name": class_name, "method_name": entity.qualified_name}
            )
        await self._add_calls_relationships(
            entity.qualified_name, entity.calls, class_context=class_name
        )

    async def _add_calls_relationships(
        self, caller_name: str, calls_list: list[str], class_context: str | None = None
    ) -> None:
        for call in calls_list:
            resolved_qn = None
            if self.call_processor and self._current_module_qn:
                try:
                    result = self.call_processor.resolve_call(
                        call,
                        self._current_module_qn,
                        class_context,
                        self._current_language or "python",
                    )
                    if result:
                        _, resolved_qn = result
                except Exception:
                    pass
            self._relationship_buffer.calls.append(
                {"caller_name": caller_name, "callee_name": resolved_qn or call}
            )

    async def _check_auto_flush(self) -> None:
        if self._entity_buffer.total_count() >= self.batch_size:
            logger.debug(f"Auto-flushing {self._entity_buffer.total_count()} buffered entities")
            await flush_entities(self.client, self._entity_buffer, self._stats)
        if self._relationship_buffer.total_count() >= self.batch_size:
            logger.debug(
                f"Auto-flushing {self._relationship_buffer.total_count()} buffered relationships"
            )
            await flush_relationships(self.client, self._relationship_buffer, self._stats)

    async def flush_entities(self) -> None:
        await flush_entities(self.client, self._entity_buffer, self._stats)

    async def flush_relationships(self) -> None:
        await flush_relationships(self.client, self._relationship_buffer, self._stats)

    async def flush_all(self) -> None:
        await flush_all(self.client, self._entity_buffer, self._relationship_buffer, self._stats)

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)
