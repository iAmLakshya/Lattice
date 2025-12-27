from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MetadataStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class FolderNode(BaseModel):
    name: str
    type: str = "directory"
    children: list[FolderNode] = Field(default_factory=list)
    description: str | None = None
    purpose: str | None = None

    model_config = {"extra": "ignore"}


class CoreFeature(BaseModel):
    name: str
    description: str
    key_files: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class TechStack(BaseModel):
    languages: list[dict[str, Any]] = Field(default_factory=list)
    frameworks: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    build_system: str | None = None
    package_manager: str | None = None

    model_config = {"extra": "ignore"}


class DependencyInfo(BaseModel):
    runtime: list[dict[str, str]] = Field(default_factory=list)
    development: list[dict[str, str]] = Field(default_factory=list)
    peer: list[dict[str, str]] = Field(default_factory=list)
    total_count: int = 0

    model_config = {"extra": "ignore"}


class EntryPoint(BaseModel):
    path: str
    type: str
    description: str
    main_function: str | None = None

    model_config = {"extra": "ignore"}


class ProjectMetadata(BaseModel):
    id: UUID | None = None
    project_name: str
    version: int = 1
    folder_structure: FolderNode | None = None
    project_overview: str | None = None
    core_features: list[CoreFeature] = Field(default_factory=list)
    architecture_diagram: str | None = None
    tech_stack: TechStack | None = None
    dependencies: DependencyInfo | None = None
    entry_points: list[EntryPoint] = Field(default_factory=list)
    generated_by: str = "claude-agent"
    generation_model: str | None = None
    generation_duration_ms: int | None = None
    generation_tokens_used: int | None = None
    status: MetadataStatus = MetadataStatus.PENDING
    created_at: datetime | None = None
    updated_at: datetime | None = None
    indexed_at: datetime | None = None

    model_config = {"extra": "ignore"}


class MetadataGenerationResult(BaseModel):
    field_name: str
    status: MetadataStatus
    value: Any | None = None
    error_message: str | None = None
    duration_ms: int = 0
    tokens_used: int = 0

    model_config = {"extra": "ignore"}
