"""Tests for the documents module - scanner, chunker, and models."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from lattice.documents.models import (
    Document,
    DocumentChunk,
    DocumentInfo,
    DocumentLink,
    DriftAnalysis,
    DriftStatus,
    ExplicitReference,
    HeadingSection,
    ImplicitLink,
    LinkType,
)
from lattice.documents.scanner import DocumentScanner, DocumentScanStatistics
from lattice.documents.chunker import DocumentChunker, create_document_chunker


class TestDriftStatus:
    def test_drift_status_values(self):
        assert DriftStatus.ALIGNED.value == "aligned"
        assert DriftStatus.MINOR_DRIFT.value == "minor_drift"
        assert DriftStatus.MAJOR_DRIFT.value == "major_drift"
        assert DriftStatus.UNKNOWN.value == "unknown"


class TestLinkType:
    def test_link_type_values(self):
        assert LinkType.EXPLICIT.value == "explicit"
        assert LinkType.IMPLICIT.value == "implicit"


class TestDocumentInfo:
    def test_document_info_creation(self, tmp_path: Path):
        doc_info = DocumentInfo(
            path=tmp_path / "test.md",
            relative_path="test.md",
            content_hash="abc123",
            size_bytes=100,
            line_count=10,
        )

        assert doc_info.relative_path == "test.md"
        assert doc_info.content_hash == "abc123"
        assert doc_info.size_bytes == 100
        assert doc_info.line_count == 10


class TestDocument:
    def test_document_creation_defaults(self):
        doc = Document(
            project_name="test-project",
            file_path="/docs/test.md",
            relative_path="test.md",
            content_hash="hash123",
        )

        assert doc.project_name == "test-project"
        assert doc.document_type == "markdown"
        assert doc.drift_status == DriftStatus.UNKNOWN
        assert doc.chunk_count == 0
        assert doc.link_count == 0

    def test_document_with_all_fields(self):
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            project_name="my-project",
            file_path="/path/to/doc.md",
            relative_path="doc.md",
            title="My Document",
            document_type="policy",
            content_hash="xyz789",
            chunk_count=5,
            link_count=3,
            drift_status=DriftStatus.MINOR_DRIFT,
            drift_score=0.3,
        )

        assert doc.id == doc_id
        assert doc.title == "My Document"
        assert doc.document_type == "policy"
        assert doc.drift_status == DriftStatus.MINOR_DRIFT
        assert doc.drift_score == 0.3


class TestDocumentChunk:
    def test_chunk_creation(self):
        doc_id = uuid4()
        chunk = DocumentChunk(
            document_id=doc_id,
            project_name="test",
            content="# Test\n\nSome content here.",
            heading_path=["Test"],
            heading_level=1,
            start_line=1,
            end_line=3,
            content_hash="chunkhash",
        )

        assert chunk.document_id == doc_id
        assert chunk.heading_level == 1
        assert "Test" in chunk.heading_path

    def test_chunk_to_qdrant_payload(self):
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=uuid4(),
            project_name="my-project",
            content="Content",
            heading_path=["Section", "Subsection"],
            heading_level=2,
            start_line=10,
            end_line=20,
            content_hash="hash",
            explicit_references=["MyClass", "my_function"],
        )

        payload = chunk.to_qdrant_payload("/docs/test.md", "api")

        assert payload["project_name"] == "my-project"
        assert payload["document_path"] == "/docs/test.md"
        assert payload["document_type"] == "api"
        assert payload["heading_path"] == ["Section", "Subsection"]
        assert payload["heading_text"] == "Subsection"
        assert payload["start_line"] == 10
        assert payload["end_line"] == 20
        assert "MyClass" in payload["explicit_references"]


class TestDocumentLink:
    def test_link_creation(self):
        link = DocumentLink(
            document_chunk_id=uuid4(),
            code_entity_qualified_name="mymodule.MyClass.my_method",
            code_entity_type="Method",
            code_file_path="/src/mymodule.py",
            link_type=LinkType.EXPLICIT,
            confidence_score=0.95,
        )

        assert link.link_type == LinkType.EXPLICIT
        assert link.confidence_score == 0.95
        assert link.code_entity_type == "Method"


class TestDriftAnalysis:
    def test_drift_analysis_creation(self):
        from datetime import datetime

        analysis = DriftAnalysis(
            document_chunk_id=uuid4(),
            document_path="/docs/api.md",
            linked_entity_qualified_name="api.handlers.process",
            analysis_trigger="code_changed",
            drift_detected=True,
            drift_severity=DriftStatus.MAJOR_DRIFT,
            drift_score=0.8,
            issues=[{"type": "behavioral", "description": "Different timeout"}],
            explanation="Code uses 30s timeout but doc says 10s",
            doc_excerpt="Timeout is 10 seconds",
            code_excerpt="timeout = 30",
            doc_version_hash="dochash",
            code_version_hash="codehash",
            analyzed_at=datetime.now(),
        )

        assert analysis.drift_detected is True
        assert analysis.drift_severity == DriftStatus.MAJOR_DRIFT
        assert len(analysis.issues) == 1


class TestHeadingSection:
    def test_heading_section_creation(self):
        section = HeadingSection(
            level=2,
            text="Overview",
            start_line=5,
            end_line=15,
            content="## Overview\n\nThis is the overview.",
            parent_headings=["Introduction"],
        )

        assert section.level == 2
        assert section.text == "Overview"
        assert "Introduction" in section.parent_headings


class TestExplicitReference:
    def test_explicit_reference_creation(self):
        ref = ExplicitReference(
            text="MyClass",
            entity_qualified_name="module.MyClass",
            pattern_type="backtick_simple",
            confidence=0.8,
            line_number=15,
        )

        assert ref.text == "MyClass"
        assert ref.confidence == 0.8
        assert ref.pattern_type == "backtick_simple"


class TestImplicitLink:
    def test_implicit_link_creation(self):
        link = ImplicitLink(
            entity_qualified_name="auth.AuthService.login",
            entity_type="Method",
            confidence=0.75,
            reasoning="Doc describes login flow matching this method",
        )

        assert link.entity_type == "Method"
        assert link.confidence == 0.75


class TestDocumentScanner:
    def test_scan_empty_directory(self, tmp_path: Path):
        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()
        assert docs == []

    def test_scan_single_markdown_file(self, tmp_path: Path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test\n\nContent here.")

        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()

        assert len(docs) == 1
        assert docs[0].relative_path == "test.md"
        assert docs[0].line_count == 3

    def test_scan_multiple_files(self, tmp_path: Path):
        (tmp_path / "doc1.md").write_text("# Doc 1")
        (tmp_path / "doc2.markdown").write_text("# Doc 2")
        (tmp_path / "doc3.mdx").write_text("# Doc 3")
        (tmp_path / "readme.txt").write_text("Not a markdown file")

        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()

        assert len(docs) == 3
        paths = {d.relative_path for d in docs}
        assert "doc1.md" in paths
        assert "doc2.markdown" in paths
        assert "doc3.mdx" in paths

    def test_scan_ignores_patterns(self, tmp_path: Path):
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.md").write_text("# Package")

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.md").write_text("# Git config")

        (tmp_path / "readme.md").write_text("# Readme")

        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()

        assert len(docs) == 1
        assert docs[0].relative_path == "readme.md"

    def test_scan_nested_directories(self, tmp_path: Path):
        docs_dir = tmp_path / "docs" / "api"
        docs_dir.mkdir(parents=True)
        (docs_dir / "auth.md").write_text("# Auth API")
        (tmp_path / "README.md").write_text("# Readme")

        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()

        assert len(docs) == 2
        paths = {d.relative_path for d in docs}
        assert "docs/api/auth.md" in paths
        assert "README.md" in paths

    def test_scan_single_file(self, tmp_path: Path):
        md_file = tmp_path / "single.md"
        md_file.write_text("# Single File\n\nContent.")

        scanner = DocumentScanner(md_file)
        docs = scanner.scan_all()

        assert len(docs) == 1
        assert docs[0].relative_path == "single.md"

    def test_scan_computes_hash(self, tmp_path: Path):
        md_file = tmp_path / "test.md"
        content = "# Test content"
        md_file.write_text(content)

        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()

        assert len(docs) == 1
        assert docs[0].content_hash is not None
        assert len(docs[0].content_hash) == 64  # SHA256 hex

    def test_scan_different_content_different_hash(self, tmp_path: Path):
        (tmp_path / "doc1.md").write_text("Content A")
        (tmp_path / "doc2.md").write_text("Content B")

        scanner = DocumentScanner(tmp_path)
        docs = scanner.scan_all()

        assert len(docs) == 2
        hashes = {d.content_hash for d in docs}
        assert len(hashes) == 2

    def test_get_statistics(self, tmp_path: Path):
        (tmp_path / "doc1.md").write_text("Line 1\nLine 2\nLine 3")
        (tmp_path / "doc2.md").write_text("Single line")

        scanner = DocumentScanner(tmp_path)
        stats = scanner.get_statistics()

        assert isinstance(stats, DocumentScanStatistics)
        assert stats.file_count == 2
        assert stats.total_lines == 4  # 3 + 1

    def test_custom_extensions(self, tmp_path: Path):
        (tmp_path / "doc.md").write_text("# Markdown")
        (tmp_path / "doc.rst").write_text("RST Doc")

        scanner = DocumentScanner(tmp_path, extensions={".rst"})
        docs = scanner.scan_all()

        assert len(docs) == 1
        assert docs[0].relative_path == "doc.rst"

    def test_custom_ignore_patterns(self, tmp_path: Path):
        drafts = tmp_path / "drafts"
        drafts.mkdir()
        (drafts / "draft.md").write_text("# Draft")
        (tmp_path / "final.md").write_text("# Final")

        scanner = DocumentScanner(tmp_path, ignore_patterns=["drafts"])
        docs = scanner.scan_all()

        assert len(docs) == 1
        assert docs[0].relative_path == "final.md"

    def test_scanner_with_sample_docs(self, sample_docs_path: Path):
        if not sample_docs_path.exists():
            pytest.skip("Sample docs not found")

        scanner = DocumentScanner(sample_docs_path)
        docs = scanner.scan_all()

        assert len(docs) >= 3
        paths = {d.relative_path for d in docs}
        assert "authentication.md" in paths
        assert "payments.md" in paths
        assert "architecture.md" in paths

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError, match="does not exist"):
            DocumentScanner("/nonexistent/path")


class TestDocumentChunker:
    @pytest.fixture
    def chunker(self):
        return DocumentChunker(max_tokens=500, overlap_tokens=50)

    def test_chunk_simple_document(self, chunker, sample_markdown_content):
        doc_id = uuid4()
        chunks = chunker.chunk_document(
            content=sample_markdown_content,
            document_id=doc_id,
            project_name="test-project",
        )

        assert len(chunks) >= 1
        assert all(c.document_id == doc_id for c in chunks)
        assert all(c.project_name == "test-project" for c in chunks)

    def test_chunk_extracts_heading_path(self, chunker):
        content = """# Main Title

## Section One

Content for section one.

### Subsection A

More content here.

## Section Two

Content for section two.
"""
        doc_id = uuid4()
        chunks = chunker.chunk_document(content, doc_id, "test")

        heading_paths = [c.heading_path for c in chunks]
        flat_headings = [h for path in heading_paths for h in path]

        assert "Main Title" in flat_headings or any(
            "Main" in h for h in flat_headings
        )

    def test_chunk_preserves_content_hash(self, chunker):
        content = "# Test\n\nSome content."
        chunks = chunker.chunk_document(content, uuid4(), "test")

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content_hash is not None
            assert len(chunk.content_hash) == 64

    def test_chunk_tracks_line_numbers(self, chunker):
        content = """# Title

## Section

Content here.
More content.
Even more content.
"""
        chunks = chunker.chunk_document(content, uuid4(), "test")

        for chunk in chunks:
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line

    def test_chunk_empty_document(self, chunker):
        chunks = chunker.chunk_document("", uuid4(), "test")
        assert len(chunks) == 1
        assert chunks[0].content == ""

    def test_chunk_no_headings(self, chunker):
        content = "This is just plain text without any headings.\n\nAnother paragraph."
        chunks = chunker.chunk_document(content, uuid4(), "test")

        assert len(chunks) >= 1
        assert chunks[0].heading_path == []
        assert chunks[0].heading_level == 0

    def test_chunk_large_document_splits(self):
        chunker = DocumentChunker(max_tokens=50, overlap_tokens=10)

        content = "# Title\n\n" + "\n".join(
            [f"Line {i} with some content to make it longer." for i in range(100)]
        )

        chunks = chunker.chunk_document(content, uuid4(), "test")

        assert len(chunks) > 1

    def test_chunk_with_code_blocks(self, chunker):
        content = """# API Reference

## Function

```python
def example():
    return "hello"
```

This function returns hello.
"""
        chunks = chunker.chunk_document(content, uuid4(), "test")

        all_content = " ".join(c.content for c in chunks)
        assert "def example" in all_content

    def test_chunk_with_sample_docs(self, sample_docs_path: Path):
        if not sample_docs_path.exists():
            pytest.skip("Sample docs not found")

        chunker = create_document_chunker()
        auth_file = sample_docs_path / "authentication.md"
        content = auth_file.read_text()

        chunks = chunker.chunk_document(content, uuid4(), "test-project")

        assert len(chunks) >= 1

        all_content = " ".join(c.content for c in chunks)
        assert "AuthService" in all_content
        assert "login" in all_content

    def test_heading_level_extraction(self, chunker):
        content = """# H1

## H2

### H3

#### H4

##### H5

###### H6

Content under H6.
"""
        chunks = chunker.chunk_document(content, uuid4(), "test")

        levels = {c.heading_level for c in chunks}
        assert len(levels) >= 1

    def test_chunk_different_documents_different_hashes(self, chunker):
        chunks1 = chunker.chunk_document("# Doc A\n\nContent A", uuid4(), "test")
        chunks2 = chunker.chunk_document("# Doc B\n\nContent B", uuid4(), "test")

        hashes1 = {c.content_hash for c in chunks1}
        hashes2 = {c.content_hash for c in chunks2}

        assert hashes1 != hashes2


class TestDocumentChunkerIntegration:
    def test_scanner_and_chunker_together(self, sample_docs_path: Path):
        if not sample_docs_path.exists():
            pytest.skip("Sample docs not found")

        scanner = DocumentScanner(sample_docs_path)
        chunker = create_document_chunker()

        total_chunks = 0
        for doc_info in scanner.scan():
            content = doc_info.path.read_text()
            doc_id = uuid4()
            chunks = chunker.chunk_document(content, doc_id, "test-project")

            total_chunks += len(chunks)

            for chunk in chunks:
                assert chunk.document_id == doc_id
                assert chunk.project_name == "test-project"
                assert chunk.content

        assert total_chunks >= 3
