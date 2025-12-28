from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field


class DriftStatus(str, Enum):
    ALIGNED = "aligned"
    MINOR_DRIFT = "minor_drift"
    MAJOR_DRIFT = "major_drift"
    UNKNOWN = "unknown"


class LinkType(str, Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"


@dataclass
class DocumentInfo:
    path: Path
    relative_path: str
    content_hash: str
    size_bytes: int
    line_count: int


class Document(BaseModel):
    id: UUID | None = None
    project_name: str
    file_path: str
    relative_path: str
    title: str | None = None
    document_type: str = "markdown"
    content_hash: str
    chunk_count: int = 0
    link_count: int = 0
    drift_status: DriftStatus = DriftStatus.UNKNOWN
    drift_score: float | None = None
    indexed_at: datetime | None = None
    last_drift_check_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentChunk(BaseModel):
    id: UUID | None = None
    document_id: UUID
    project_name: str
    content: str
    heading_path: list[str] = Field(default_factory=list)
    heading_level: int = 0
    start_line: int
    end_line: int
    content_hash: str
    embedding_id: str | None = None
    explicit_references: list[str] = Field(default_factory=list)
    drift_status: DriftStatus = DriftStatus.UNKNOWN
    drift_score: float | None = None
    last_drift_check_at: datetime | None = None

    def to_qdrant_payload(self, document_path: str, document_type: str) -> dict:
        return {
            "chunk_id": str(self.id),
            "project_name": self.project_name,
            "document_path": document_path,
            "document_type": document_type,
            "heading_path": self.heading_path,
            "heading_level": self.heading_level,
            "heading_text": self.heading_path[-1] if self.heading_path else "",
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content_hash": self.content_hash,
            "explicit_references": self.explicit_references,
        }


class DocumentLink(BaseModel):
    id: UUID | None = None
    document_chunk_id: UUID
    code_entity_qualified_name: str
    code_entity_type: str
    code_file_path: str
    link_type: LinkType
    confidence_score: float
    line_range_start: int | None = None
    line_range_end: int | None = None
    code_version_hash: str | None = None
    reasoning: str | None = None
    created_at: datetime | None = None
    last_calibrated_at: datetime | None = None


class DriftAnalysis(BaseModel):
    id: UUID | None = None
    document_chunk_id: UUID
    document_path: str
    linked_entity_qualified_name: str
    analysis_trigger: str
    drift_detected: bool
    drift_severity: DriftStatus
    drift_score: float
    issues: list[dict] = Field(default_factory=list)
    explanation: str
    doc_excerpt: str
    code_excerpt: str
    doc_version_hash: str
    code_version_hash: str
    analyzed_at: datetime


@dataclass
class HeadingSection:
    level: int
    text: str
    start_line: int
    end_line: int
    content: str
    parent_headings: list[str] = field(default_factory=list)


@dataclass
class ExplicitReference:
    text: str
    entity_qualified_name: str
    pattern_type: str
    confidence: float
    line_number: int


@dataclass
class ImplicitLink:
    entity_qualified_name: str
    entity_type: str
    confidence: float
    reasoning: str
