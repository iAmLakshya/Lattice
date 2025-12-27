"""Tests for metadata generator."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from lattice.metadata.generator import MetadataGenerator, GenerationProgress
from lattice.metadata.models import (
    MetadataStatus,
    FolderNode,
    TechStack,
    DependencyInfo,
    EntryPoint,
    CoreFeature,
)


class TestGenerationProgress:
    """Tests for GenerationProgress dataclass."""

    def test_initial_state(self):
        progress = GenerationProgress()
        assert progress.current_field == ""
        assert progress.completed_fields == []
        assert progress.failed_fields == []
        assert progress.total_fields == 7
        assert progress.tokens_used == 0
        assert progress.elapsed_ms == 0

    def test_progress_percentage(self):
        progress = GenerationProgress()
        assert progress.progress_percentage == 0.0

        progress.completed_fields = ["field1", "field2"]
        assert progress.progress_percentage == pytest.approx(28.57, rel=0.01)

        progress.failed_fields = ["field3"]
        assert progress.progress_percentage == pytest.approx(42.86, rel=0.01)


class TestMetadataGenerator:
    """Tests for MetadataGenerator class."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a generator with a temp repo path."""
        return MetadataGenerator(
            repo_path=tmp_path,
            project_name="test_project",
        )

    def test_initialization(self, generator, tmp_path):
        assert generator.repo_path == tmp_path
        assert generator.project_name == "test_project"
        assert generator.max_budget_usd == 0.50

    def test_generation_order(self, generator):
        expected = [
            "folder_structure",
            "tech_stack",
            "dependencies",
            "entry_points",
            "core_features",
            "project_overview",
            "architecture_diagram",
        ]
        assert generator.GENERATION_ORDER == expected


class TestJsonExtraction:
    """Tests for JSON extraction from agent responses."""

    @pytest.fixture
    def generator(self, tmp_path):
        return MetadataGenerator(
            repo_path=tmp_path,
            project_name="test",
        )

    def test_extract_json_from_code_block(self, generator):
        content = '''
Here is the analysis:

```json
{"name": "test", "type": "directory"}
```

That's the structure.
'''
        result = generator._extract_json(content)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "test"

    def test_extract_json_without_code_block(self, generator):
        content = '''
The structure is: {"name": "root", "children": []}
'''
        result = generator._extract_json(content)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["name"] == "root"

    def test_extract_json_array(self, generator):
        # Array should come before any object for proper extraction
        content = '''
Features:
[{"name": "Auth"}, {"name": "Search"}]
'''
        result = generator._extract_json(content)
        assert result is not None
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_extract_nested_json(self, generator):
        content = '''
```json
{
  "languages": [
    {"name": "Python", "version": "3.11"}
  ],
  "frameworks": []
}
```
'''
        result = generator._extract_json(content)
        assert result is not None
        parsed = json.loads(result)
        assert "languages" in parsed

    def test_extract_json_no_json(self, generator):
        content = "This is plain text without JSON"
        result = generator._extract_json(content)
        assert result is None


class TestParseFieldResponse:
    """Tests for parsing field responses into models."""

    @pytest.fixture
    def generator(self, tmp_path):
        return MetadataGenerator(
            repo_path=tmp_path,
            project_name="test",
        )

    def test_parse_folder_structure(self, generator):
        content = '''
```json
{
  "name": "project",
  "type": "directory",
  "children": [
    {"name": "src", "type": "directory"},
    {"name": "README.md", "type": "file"}
  ]
}
```
'''
        result = generator._parse_field_response("folder_structure", content)
        assert isinstance(result, FolderNode)
        assert result.name == "project"
        assert len(result.children) == 2

    def test_parse_tech_stack(self, generator):
        content = '''
```json
{
  "languages": [{"name": "Python", "version": "3.11", "usage_percentage": 100}],
  "frameworks": [{"name": "FastAPI", "purpose": "API"}],
  "tools": ["pytest", "mypy"],
  "build_system": "hatch",
  "package_manager": "pip"
}
```
'''
        result = generator._parse_field_response("tech_stack", content)
        assert isinstance(result, TechStack)
        assert len(result.languages) == 1
        assert result.build_system == "hatch"

    def test_parse_dependencies(self, generator):
        content = '''
```json
{
  "runtime": [{"name": "openai", "version": ">=1.0"}],
  "development": [{"name": "pytest"}],
  "peer": [],
  "total_count": 2
}
```
'''
        result = generator._parse_field_response("dependencies", content)
        assert isinstance(result, DependencyInfo)
        assert result.total_count == 2

    def test_parse_entry_points(self, generator):
        content = '''
```json
[
  {"path": "src/main.py", "type": "cli", "description": "CLI entry"},
  {"path": "src/api/app.py", "type": "api", "description": "API server"}
]
```
'''
        result = generator._parse_field_response("entry_points", content)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(ep, EntryPoint) for ep in result)

    def test_parse_core_features(self, generator):
        content = '''
```json
[
  {
    "name": "Graph Search",
    "description": "Search code relationships",
    "key_files": ["src/graph/search.py"],
    "related_entities": ["GraphSearch"]
  }
]
```
'''
        result = generator._parse_field_response("core_features", content)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], CoreFeature)
        assert result[0].name == "Graph Search"

    def test_parse_project_overview(self, generator):
        content = '''
This is a code intelligence tool.

It uses graph and vector search.

The main components are parsers and indexers.
'''
        result = generator._parse_field_response("project_overview", content)
        assert isinstance(result, str)
        assert "code intelligence" in result

    def test_parse_architecture_diagram(self, generator):
        content = '''
```
+--------+     +--------+
| Parser | --> | Graph  |
+--------+     +--------+
```
'''
        result = generator._parse_field_response("architecture_diagram", content)
        assert isinstance(result, str)
        assert "+--------+" in result

    def test_parse_invalid_json_raises(self, generator):
        content = "not valid json at all"
        with pytest.raises(ValueError, match="No JSON found"):
            generator._parse_field_response("tech_stack", content)


class TestStripCodeBlocks:
    """Tests for stripping markdown code blocks."""

    @pytest.fixture
    def generator(self, tmp_path):
        return MetadataGenerator(
            repo_path=tmp_path,
            project_name="test",
        )

    def test_strip_json_block(self, generator):
        content = "```json\n{\"key\": \"value\"}\n```"
        result = generator._strip_code_blocks(content)
        assert result == '{"key": "value"}'

    def test_strip_plain_block(self, generator):
        content = "```\nsome text\n```"
        result = generator._strip_code_blocks(content)
        assert result == "some text"

    def test_no_blocks(self, generator):
        content = "just plain text"
        result = generator._strip_code_blocks(content)
        assert result == "just plain text"
