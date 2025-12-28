"""Graph builder for constructing knowledge graph from parsed code."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.infrastructure.memgraph.entity_builder import EntityBuilder
from lattice.infrastructure.memgraph.queries import FileQueries, ProjectQueries
from lattice.infrastructure.memgraph.relationship_builder import RelationshipBuilder
from lattice.parsing.api import ParsedFile
from lattice.shared.types import EntityType

if TYPE_CHECKING:
    from lattice.parsing.api import CallProcessor


class GraphBuilder:
    """Builds the knowledge graph from parsed code files.

    Coordinates EntityBuilder and RelationshipBuilder for graph construction.
    """

    def __init__(
        self,
        client: MemgraphClient,
        call_processor: CallProcessor | None = None,
        project_name: str | None = None,
        project_id: str | None = None,
    ):
        self.client = client
        self.project_name = project_name
        self.project_id = project_id if project_id is not None else project_name

        self._entity_builder = EntityBuilder(client, self.project_id)
        self._relationship_builder = RelationshipBuilder(client, call_processor)

    async def create_project(self, name: str, path: str) -> None:
        await self.client.execute(
            ProjectQueries.CREATE_PROJECT,
            {"name": name, "path": path},
        )

    async def file_needs_update(self, path: str, content_hash: str) -> bool:
        result = await self.client.execute(
            FileQueries.GET_FILE_BY_HASH,
            {"path": path, "hash": content_hash},
        )
        return len(result) == 0

    async def delete_file_entities(self, path: str) -> None:
        await self.client.execute(
            FileQueries.DELETE_FILE_ENTITIES,
            {"path": path},
        )

    async def delete_calls_for_file(self, path: str) -> None:
        await self._relationship_builder.delete_calls_for_file(path)

    async def rebuild_calls_for_file(self, path: str) -> None:
        await self._relationship_builder.rebuild_calls_for_file(path)

    async def build_from_parsed_file(self, parsed_file: ParsedFile) -> None:
        file_path = str(parsed_file.file_info.path)
        language = parsed_file.file_info.language.value
        module_qn = self._file_to_module_qn(parsed_file.file_info.relative_path)

        self._relationship_builder.set_context(module_qn, language)

        await self._create_file_node(parsed_file, file_path)
        await self._process_imports(parsed_file, file_path)
        await self._process_entities(parsed_file, file_path)

    async def _create_file_node(self, parsed_file: ParsedFile, file_path: str) -> None:
        await self.client.execute(
            FileQueries.CREATE_FILE,
            {
                "path": file_path,
                "name": parsed_file.file_info.path.name,
                "language": parsed_file.file_info.language.value,
                "hash": parsed_file.file_info.content_hash,
                "line_count": parsed_file.file_info.line_count,
                "summary": parsed_file.summary,
            },
        )

    async def _process_imports(self, parsed_file: ParsedFile, file_path: str) -> None:
        for imp in parsed_file.imports:
            await self._entity_builder.create_import(
                name=imp.name,
                file_path=file_path,
                alias=imp.alias,
                source=imp.source,
                is_external=imp.is_external,
                line_number=imp.line_number,
            )
            await self._relationship_builder.create_file_imports(file_path, imp.name)

    async def _process_entities(self, parsed_file: ParsedFile, file_path: str) -> None:
        for entity in parsed_file.entities:
            await self._create_entity_with_relationships(entity, file_path)

    async def _create_entity_with_relationships(
        self, entity, file_path: str, parent_class: str | None = None
    ) -> None:
        await self._entity_builder.create_entity(entity, file_path, parent_class)

        if entity.type == EntityType.CLASS:
            await self._relationship_builder.create_file_defines_class(
                file_path, entity.qualified_name
            )
            for base_class in entity.base_classes:
                await self._relationship_builder.create_class_extends(
                    entity.qualified_name, base_class
                )
            for child in entity.children:
                if child.type == EntityType.METHOD:
                    await self._create_method_with_relationships(
                        child, file_path, entity.qualified_name
                    )

        elif entity.type == EntityType.FUNCTION:
            await self._relationship_builder.create_file_defines_function(
                file_path, entity.qualified_name
            )
            await self._relationship_builder.create_calls_relationships(
                entity.qualified_name, entity.calls
            )

    async def _create_method_with_relationships(
        self, entity, file_path: str, parent_class: str
    ) -> None:
        await self._entity_builder.create_method(entity, file_path, parent_class)
        await self._relationship_builder.create_class_defines_method(
            parent_class, entity.qualified_name
        )
        await self._relationship_builder.create_calls_relationships(
            entity.qualified_name, entity.calls, class_context=parent_class
        )

    def _file_to_module_qn(self, relative_path: str) -> str:
        path = Path(relative_path)
        parts = list(path.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        base = f"{self.project_name}.{'.'.join(parts)}" if parts else self.project_name
        return base if self.project_name else ".".join(parts)
