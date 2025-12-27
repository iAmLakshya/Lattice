"""Tests for metadata models."""

import pytest
from uuid import uuid4
from datetime import datetime

from lattice.metadata.models import (
    CoreFeature,
    DependencyInfo,
    EntryPoint,
    FolderNode,
    MetadataGenerationResult,
    MetadataStatus,
    ProjectMetadata,
    TechStack,
)


class TestMetadataStatus:
    """Tests for MetadataStatus enum."""

    def test_status_values(self):
        assert MetadataStatus.PENDING.value == "pending"
        assert MetadataStatus.GENERATING.value == "generating"
        assert MetadataStatus.COMPLETED.value == "completed"
        assert MetadataStatus.FAILED.value == "failed"
        assert MetadataStatus.PARTIAL.value == "partial"


class TestFolderNode:
    """Tests for FolderNode model."""

    def test_basic_folder(self):
        node = FolderNode(name="src", type="directory")
        assert node.name == "src"
        assert node.type == "directory"
        assert node.children == []
        assert node.description is None
        assert node.purpose is None

    def test_folder_with_children(self):
        child = FolderNode(name="main.py", type="file", description="Entry point")
        parent = FolderNode(
            name="src",
            type="directory",
            children=[child],
            purpose="Source code",
        )
        assert len(parent.children) == 1
        assert parent.children[0].name == "main.py"
        assert parent.purpose == "Source code"

    def test_nested_folders(self):
        """Test recursive folder structure."""
        leaf = FolderNode(name="utils.py", type="file")
        mid = FolderNode(name="helpers", type="directory", children=[leaf])
        root = FolderNode(name="src", type="directory", children=[mid])

        assert root.children[0].children[0].name == "utils.py"

    def test_from_dict(self):
        data = {
            "name": "project",
            "type": "directory",
            "description": "Root",
            "children": [
                {"name": "src", "type": "directory"},
                {"name": "README.md", "type": "file"},
            ],
        }
        node = FolderNode.model_validate(data)
        assert node.name == "project"
        assert len(node.children) == 2


class TestCoreFeature:
    """Tests for CoreFeature model."""

    def test_basic_feature(self):
        feature = CoreFeature(
            name="Authentication",
            description="JWT-based user authentication",
        )
        assert feature.name == "Authentication"
        assert feature.description == "JWT-based user authentication"
        assert feature.key_files == []
        assert feature.related_entities == []

    def test_feature_with_files(self):
        feature = CoreFeature(
            name="Graph Search",
            description="Searches code relationships",
            key_files=["src/graph/search.py", "src/graph/builder.py"],
            related_entities=["GraphSearch", "GraphBuilder"],
        )
        assert len(feature.key_files) == 2
        assert len(feature.related_entities) == 2


class TestTechStack:
    """Tests for TechStack model."""

    def test_empty_tech_stack(self):
        stack = TechStack()
        assert stack.languages == []
        assert stack.frameworks == []
        assert stack.tools == []
        assert stack.build_system is None
        assert stack.package_manager is None

    def test_full_tech_stack(self):
        stack = TechStack(
            languages=[
                {"name": "Python", "version": "3.11", "usage_percentage": 85},
                {"name": "TypeScript", "version": "5.0", "usage_percentage": 15},
            ],
            frameworks=[
                {"name": "FastAPI", "version": "0.100", "purpose": "API"},
            ],
            tools=["Docker", "pytest"],
            build_system="hatch",
            package_manager="pip",
        )
        assert len(stack.languages) == 2
        assert stack.languages[0]["name"] == "Python"
        assert stack.build_system == "hatch"


class TestDependencyInfo:
    """Tests for DependencyInfo model."""

    def test_empty_dependencies(self):
        deps = DependencyInfo()
        assert deps.runtime == []
        assert deps.development == []
        assert deps.peer == []
        assert deps.total_count == 0

    def test_with_dependencies(self):
        deps = DependencyInfo(
            runtime=[
                {"name": "openai", "version": ">=1.0", "purpose": "LLM API"},
            ],
            development=[
                {"name": "pytest", "version": ">=8.0", "purpose": "Testing"},
            ],
            total_count=2,
        )
        assert len(deps.runtime) == 1
        assert len(deps.development) == 1
        assert deps.total_count == 2


class TestEntryPoint:
    """Tests for EntryPoint model."""

    def test_cli_entry_point(self):
        ep = EntryPoint(
            path="src/main.py",
            type="cli",
            description="CLI entry point",
            main_function="main",
        )
        assert ep.path == "src/main.py"
        assert ep.type == "cli"
        assert ep.main_function == "main"

    def test_api_entry_point(self):
        ep = EntryPoint(
            path="src/api/app.py",
            type="api",
            description="FastAPI application",
        )
        assert ep.type == "api"
        assert ep.main_function is None


class TestProjectMetadata:
    """Tests for ProjectMetadata model."""

    def test_minimal_metadata(self):
        meta = ProjectMetadata(project_name="myproject")
        assert meta.project_name == "myproject"
        assert meta.version == 1
        assert meta.status == MetadataStatus.PENDING
        assert meta.generated_by == "claude-agent"

    def test_full_metadata(self):
        meta = ProjectMetadata(
            id=uuid4(),
            project_name="lattice",
            version=3,
            folder_structure=FolderNode(name="lattice", type="directory"),
            project_overview="A code intelligence tool",
            core_features=[
                CoreFeature(name="Search", description="Code search"),
            ],
            architecture_diagram="```\n+----+\n|Box|\n+----+\n```",
            tech_stack=TechStack(languages=[{"name": "Python"}]),
            dependencies=DependencyInfo(total_count=10),
            entry_points=[
                EntryPoint(path="main.py", type="cli", description="CLI"),
            ],
            generation_model="claude-code-sdk",
            generation_duration_ms=5000,
            generation_tokens_used=1000,
            status=MetadataStatus.COMPLETED,
            created_at=datetime.now(),
        )
        assert meta.version == 3
        assert meta.status == MetadataStatus.COMPLETED
        assert len(meta.core_features) == 1
        assert len(meta.entry_points) == 1

    def test_serialization_roundtrip(self):
        meta = ProjectMetadata(
            project_name="test",
            folder_structure=FolderNode(
                name="root",
                children=[FolderNode(name="src", type="directory")],
            ),
            core_features=[
                CoreFeature(name="Feature1", description="Desc"),
            ],
        )

        # Serialize to JSON and back
        json_str = meta.model_dump_json()
        restored = ProjectMetadata.model_validate_json(json_str)

        assert restored.project_name == "test"
        assert restored.folder_structure.name == "root"
        assert len(restored.folder_structure.children) == 1


class TestMetadataGenerationResult:
    """Tests for MetadataGenerationResult model."""

    def test_successful_result(self):
        result = MetadataGenerationResult(
            field_name="tech_stack",
            status=MetadataStatus.COMPLETED,
            value={"languages": [{"name": "Python"}]},
            duration_ms=500,
            tokens_used=100,
        )
        assert result.field_name == "tech_stack"
        assert result.status == MetadataStatus.COMPLETED
        assert result.error_message is None

    def test_failed_result(self):
        result = MetadataGenerationResult(
            field_name="architecture_diagram",
            status=MetadataStatus.FAILED,
            error_message="Agent timed out",
            duration_ms=30000,
        )
        assert result.status == MetadataStatus.FAILED
        assert result.error_message == "Agent timed out"
        assert result.value is None
