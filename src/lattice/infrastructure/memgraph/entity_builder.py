"""Entity creation for knowledge graph construction."""

from __future__ import annotations

import logging

from lattice.infrastructure.memgraph.client import MemgraphClient
from lattice.infrastructure.memgraph.queries import EntityQueries
from lattice.parsing.api import CodeEntity
from lattice.shared.types import EntityType

logger = logging.getLogger(__name__)


class EntityBuilder:
    """Handles creation of entity nodes in the knowledge graph."""

    def __init__(self, client: MemgraphClient, project_id: str | None = None):
        self._client = client
        self._project_id = project_id

    def build_base_properties(
        self,
        entity: CodeEntity,
        file_path: str,
    ) -> dict:
        return {
            "qualified_name": entity.qualified_name,
            "name": entity.name,
            "signature": entity.signature,
            "docstring": entity.docstring,
            "summary": None,
            "start_line": entity.start_line,
            "end_line": entity.end_line,
            "file_path": file_path,
            "project_id": self._project_id,
        }

    async def create_entity(
        self,
        entity: CodeEntity,
        file_path: str,
        parent_class: str | None = None,
    ) -> None:
        if entity.type == EntityType.CLASS:
            await self.create_class(entity, file_path)
        elif entity.type == EntityType.FUNCTION:
            await self.create_function(entity, file_path)
        elif entity.type == EntityType.METHOD:
            await self.create_method(entity, file_path, parent_class)

    async def create_class(self, entity: CodeEntity, file_path: str) -> None:
        properties = self.build_base_properties(entity, file_path)
        await self._client.execute(EntityQueries.CREATE_CLASS, properties)

    async def create_function(self, entity: CodeEntity, file_path: str) -> None:
        properties = self.build_base_properties(entity, file_path)
        properties["is_async"] = entity.is_async
        await self._client.execute(EntityQueries.CREATE_FUNCTION, properties)

    async def create_method(
        self,
        entity: CodeEntity,
        file_path: str,
        parent_class: str | None,
    ) -> None:
        class_name = parent_class or entity.parent_class
        properties = self.build_base_properties(entity, file_path)
        properties.update(
            {
                "is_async": entity.is_async,
                "is_static": entity.is_static,
                "is_classmethod": entity.is_classmethod,
                "parent_class": class_name,
            }
        )
        await self._client.execute(EntityQueries.CREATE_METHOD, properties)

    async def create_import(
        self,
        name: str,
        file_path: str,
        alias: str | None,
        source: str | None,
        is_external: bool,
        line_number: int,
    ) -> None:
        await self._client.execute(
            EntityQueries.CREATE_IMPORT,
            {
                "name": name,
                "file_path": file_path,
                "alias": alias,
                "source": source,
                "is_external": is_external,
                "line_number": line_number,
            },
        )
