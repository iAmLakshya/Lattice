import json
import logging
from uuid import UUID

from lattice.infrastructure.postgres import PostgresClient
from lattice.metadata.models import (
    CoreFeature,
    DependencyInfo,
    EntryPoint,
    FolderNode,
    MetadataStatus,
    ProjectMetadata,
    TechStack,
)

logger = logging.getLogger(__name__)


class MetadataRepository:
    def __init__(self, postgres: PostgresClient):
        self._postgres = postgres

    async def get_by_project_name(self, project_name: str) -> ProjectMetadata | None:
        query = "SELECT * FROM project_metadata WHERE project_name = $1"
        row = await self._postgres.fetchrow(query, project_name)

        if row is None:
            return None

        return self._row_to_metadata(row)

    async def get_by_id(self, metadata_id: UUID) -> ProjectMetadata | None:
        query = "SELECT * FROM project_metadata WHERE id = $1"
        row = await self._postgres.fetchrow(query, metadata_id)

        if row is None:
            return None

        return self._row_to_metadata(row)

    async def upsert(self, metadata: ProjectMetadata) -> ProjectMetadata:
        folder_json = (
            metadata.folder_structure.model_dump_json() if metadata.folder_structure else None
        )
        features_json = (
            json.dumps([f.model_dump() for f in metadata.core_features])
            if metadata.core_features
            else "[]"
        )
        tech_stack_json = metadata.tech_stack.model_dump_json() if metadata.tech_stack else None
        deps_json = metadata.dependencies.model_dump_json() if metadata.dependencies else None
        entry_points_json = (
            json.dumps([e.model_dump() for e in metadata.entry_points])
            if metadata.entry_points
            else "[]"
        )

        query = """
            INSERT INTO project_metadata (
                project_name, version,
                folder_structure, project_overview, core_features,
                architecture_diagram, tech_stack, dependencies, entry_points,
                generated_by, generation_model, generation_duration_ms,
                generation_tokens_used, status, indexed_at
            ) VALUES (
                $1, 1,
                $2, $3, $4,
                $5, $6, $7, $8,
                $9, $10, $11,
                $12, $13, $14
            )
            ON CONFLICT (project_name) DO UPDATE SET
                version = project_metadata.version + 1,
                folder_structure = EXCLUDED.folder_structure,
                project_overview = EXCLUDED.project_overview,
                core_features = EXCLUDED.core_features,
                architecture_diagram = EXCLUDED.architecture_diagram,
                tech_stack = EXCLUDED.tech_stack,
                dependencies = EXCLUDED.dependencies,
                entry_points = EXCLUDED.entry_points,
                generated_by = EXCLUDED.generated_by,
                generation_model = EXCLUDED.generation_model,
                generation_duration_ms = EXCLUDED.generation_duration_ms,
                generation_tokens_used = EXCLUDED.generation_tokens_used,
                status = EXCLUDED.status,
                indexed_at = EXCLUDED.indexed_at,
                updated_at = NOW()
            RETURNING *
        """

        row = await self._postgres.fetchrow(
            query,
            metadata.project_name,
            folder_json,
            metadata.project_overview,
            features_json,
            metadata.architecture_diagram,
            tech_stack_json,
            deps_json,
            entry_points_json,
            metadata.generated_by,
            metadata.generation_model,
            metadata.generation_duration_ms,
            metadata.generation_tokens_used,
            metadata.status.value,
            metadata.indexed_at,
        )

        result = self._row_to_metadata(row)
        logger.info(
            f"Upserted metadata for project '{result.project_name}' "
            f"(version {result.version}, status: {result.status.value})"
        )
        return result

    async def delete(self, project_name: str) -> bool:
        query = "DELETE FROM project_metadata WHERE project_name = $1"
        result = await self._postgres.execute(query, project_name)
        deleted = result == "DELETE 1"

        if deleted:
            logger.info(f"Deleted metadata for project '{project_name}'")
        else:
            logger.warning(f"No metadata found for project '{project_name}'")

        return deleted

    async def list_all(self) -> list[ProjectMetadata]:
        query = "SELECT * FROM project_metadata ORDER BY project_name"
        rows = await self._postgres.fetch(query)
        return [self._row_to_metadata(row) for row in rows]

    async def update_status(
        self, project_name: str, status: MetadataStatus
    ) -> ProjectMetadata | None:
        query = """
            UPDATE project_metadata
            SET status = $2, updated_at = NOW()
            WHERE project_name = $1
            RETURNING *
        """
        row = await self._postgres.fetchrow(query, project_name, status.value)

        if row is None:
            return None

        return self._row_to_metadata(row)

    async def log_generation(
        self,
        metadata_id: UUID,
        field_name: str,
        status: MetadataStatus,
        error_message: str | None = None,
        duration_ms: int | None = None,
        tokens_used: int | None = None,
    ) -> None:
        query = """
            INSERT INTO metadata_generation_log (
                project_metadata_id, field_name, status,
                error_message, duration_ms, tokens_used
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """
        await self._postgres.execute(
            query,
            metadata_id,
            field_name,
            status.value,
            error_message,
            duration_ms,
            tokens_used,
        )

    async def get_generation_logs(self, metadata_id: UUID) -> list[dict]:
        query = """
            SELECT field_name, status, error_message, duration_ms, tokens_used, created_at
            FROM metadata_generation_log
            WHERE project_metadata_id = $1
            ORDER BY created_at DESC
        """
        rows = await self._postgres.fetch(query, metadata_id)
        return [dict(row) for row in rows]

    def _row_to_metadata(self, row) -> ProjectMetadata:
        folder_structure = None
        if row["folder_structure"]:
            folder_data = (
                json.loads(row["folder_structure"])
                if isinstance(row["folder_structure"], str)
                else row["folder_structure"]
            )
            folder_structure = FolderNode.model_validate(folder_data)

        core_features = []
        if row["core_features"]:
            features_data = (
                json.loads(row["core_features"])
                if isinstance(row["core_features"], str)
                else row["core_features"]
            )
            core_features = [CoreFeature.model_validate(f) for f in features_data]

        tech_stack = None
        if row["tech_stack"]:
            tech_data = (
                json.loads(row["tech_stack"])
                if isinstance(row["tech_stack"], str)
                else row["tech_stack"]
            )
            tech_stack = TechStack.model_validate(tech_data)

        dependencies = None
        if row["dependencies"]:
            deps_data = (
                json.loads(row["dependencies"])
                if isinstance(row["dependencies"], str)
                else row["dependencies"]
            )
            dependencies = DependencyInfo.model_validate(deps_data)

        entry_points = []
        if row["entry_points"]:
            entry_data = (
                json.loads(row["entry_points"])
                if isinstance(row["entry_points"], str)
                else row["entry_points"]
            )
            entry_points = [EntryPoint.model_validate(e) for e in entry_data]

        return ProjectMetadata(
            id=row["id"],
            project_name=row["project_name"],
            version=row["version"],
            folder_structure=folder_structure,
            project_overview=row["project_overview"],
            core_features=core_features,
            architecture_diagram=row["architecture_diagram"],
            tech_stack=tech_stack,
            dependencies=dependencies,
            entry_points=entry_points,
            generated_by=row["generated_by"],
            generation_model=row["generation_model"],
            generation_duration_ms=row["generation_duration_ms"],
            generation_tokens_used=row["generation_tokens_used"],
            status=MetadataStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            indexed_at=row["indexed_at"],
        )
