"""Project manager for Lattice."""

import logging
from typing import Any

from lattice.infrastructure.memgraph import MemgraphClient
from lattice.infrastructure.qdrant import QdrantManager
from lattice.projects.cleanup import ProjectCleanupService
from lattice.projects.models import Project
from lattice.projects.repository import ProjectRepository

logger = logging.getLogger(__name__)


async def create_project_manager() -> "ProjectManager":
    memgraph = MemgraphClient()
    await memgraph.connect()

    qdrant = QdrantManager()
    await qdrant.connect()

    return ProjectManager(
        memgraph=memgraph,
        qdrant=qdrant,
        owns_connections=True,
    )


class ProjectManager:
    """Manages Lattice projects and their indexes."""

    def __init__(
        self,
        memgraph: MemgraphClient,
        qdrant: QdrantManager,
        owns_connections: bool = False,
    ):
        self._memgraph = memgraph
        self._qdrant = qdrant
        self._owns_connections = owns_connections
        self._repository = ProjectRepository(self._memgraph)
        self._cleanup_service = ProjectCleanupService(self._qdrant)

    async def connect(self) -> None:
        logger.info("Project manager connected to databases")

    async def close(self) -> None:
        if self._owns_connections:
            await self._memgraph.close()
            await self._qdrant.close()

        logger.info("Project manager disconnected from databases")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def list_projects(self) -> list[Project]:
        return await self._repository.list_all()

    async def get_project(self, name: str) -> Project | None:
        return await self._repository.get_by_name(name)

    async def delete_project(self, name: str) -> bool:
        project = await self._repository.get_by_name(name)
        if not project:
            logger.warning(f"Project '{name}' not found for deletion")
            return False

        for index in project.indexes:
            await self._cleanup_service.delete_from_qdrant(index.path)

        await self._repository.delete(name)

        logger.info(f"Successfully deleted project '{name}'")
        return True

    async def delete_index(self, project_name: str, path: str) -> bool:
        await self._cleanup_service.delete_from_qdrant(path)
        await self._repository.delete_index(path)
        await self._repository.delete_empty_project(project_name)

        logger.info(f"Successfully deleted index at path '{path}' from project '{project_name}'")
        return True

    async def get_project_stats(self, name: str) -> dict[str, Any]:
        project = await self._repository.get_by_name(name)
        if not project:
            logger.warning(f"Project '{name}' not found for stats")
            return {}

        stats = {
            "name": project.name,
            "created_at": project.created_at,
            "last_indexed_at": project.last_indexed_at,
            "total_files": project.total_files,
            "total_entities": project.total_entities,
            "total_chunks": project.total_chunks,
            "indexes": [idx.to_dict() for idx in project.indexes],
        }

        logger.debug(f"Generated stats for project '{name}'")
        return stats

    async def get_chunk_count(self, path: str) -> int:
        return await self._cleanup_service.get_chunk_count(path)
