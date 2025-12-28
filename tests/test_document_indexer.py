"""Tests for DocumentIndexer and DocumentSearcher."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from lattice.documents.indexer import DocumentIndexer, DocumentSearcher, DocumentSearchResult
from lattice.documents.models import DocumentChunk


class TestDocumentIndexer:
    @pytest.fixture
    def mock_qdrant(self):
        qdrant = AsyncMock()
        qdrant.upsert = AsyncMock()
        qdrant.delete = AsyncMock()
        qdrant.file_needs_update = AsyncMock(return_value=True)
        return qdrant

    @pytest.fixture
    def mock_embedder(self):
        embedder = AsyncMock()
        embedder.embed = AsyncMock(return_value=[0.1] * 1536)
        embedder.embed_with_progress = AsyncMock(
            return_value=[[0.1] * 1536, [0.2] * 1536]
        )
        return embedder

    @pytest.fixture
    def indexer(self, mock_qdrant, mock_embedder):
        return DocumentIndexer(mock_qdrant, mock_embedder)

    @pytest.fixture
    def sample_chunks(self):
        doc_id = uuid4()
        return [
            DocumentChunk(
                id=uuid4(),
                document_id=doc_id,
                project_name="test-project",
                content="# Overview\n\nThis is the overview section.",
                heading_path=["Overview"],
                heading_level=1,
                start_line=1,
                end_line=3,
                content_hash="hash1",
            ),
            DocumentChunk(
                id=uuid4(),
                document_id=doc_id,
                project_name="test-project",
                content="## Details\n\nMore details here.",
                heading_path=["Overview", "Details"],
                heading_level=2,
                start_line=5,
                end_line=7,
                content_hash="hash2",
            ),
        ]

    @pytest.mark.asyncio
    async def test_index_chunks(self, indexer, sample_chunks, mock_qdrant, mock_embedder):
        count = await indexer.index_chunks(
            chunks=sample_chunks,
            document_path="/docs/test.md",
            document_type="markdown",
        )

        assert count == 2
        mock_embedder.embed_with_progress.assert_called_once()
        mock_qdrant.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_chunks_empty_list(self, indexer, mock_qdrant, mock_embedder):
        count = await indexer.index_chunks(
            chunks=[],
            document_path="/docs/empty.md",
            document_type="markdown",
        )

        assert count == 0
        mock_embedder.embed_with_progress.assert_not_called()
        mock_qdrant.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_chunks_with_progress(
        self, indexer, sample_chunks, mock_embedder
    ):
        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        await indexer.index_chunks(
            chunks=sample_chunks,
            document_path="/docs/test.md",
            document_type="api",
            progress_callback=progress_callback,
        )

        mock_embedder.embed_with_progress.assert_called_once()
        call_kwargs = mock_embedder.embed_with_progress.call_args[1]
        assert "progress_callback" in call_kwargs

    @pytest.mark.asyncio
    async def test_index_chunks_creates_correct_payloads(
        self, indexer, sample_chunks, mock_qdrant
    ):
        await indexer.index_chunks(
            chunks=sample_chunks,
            document_path="/docs/test.md",
            document_type="policy",
        )

        call_args = mock_qdrant.upsert.call_args
        payloads = call_args[1]["payloads"]

        assert len(payloads) == 2
        assert payloads[0]["document_path"] == "/docs/test.md"
        assert payloads[0]["document_type"] == "policy"
        assert payloads[0]["project_name"] == "test-project"

    @pytest.mark.asyncio
    async def test_delete_document_chunks(self, indexer, mock_qdrant):
        await indexer.delete_document_chunks("/docs/old.md")

        mock_qdrant.delete.assert_called_once()
        call_args = mock_qdrant.delete.call_args
        assert call_args[0][1]["document_path"] == "/docs/old.md"

    @pytest.mark.asyncio
    async def test_document_needs_update(self, indexer, mock_qdrant):
        mock_qdrant.file_needs_update.return_value = True

        needs_update = await indexer.document_needs_update("/docs/test.md", "newhash")

        assert needs_update is True
        mock_qdrant.file_needs_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_does_not_need_update(self, indexer, mock_qdrant):
        mock_qdrant.file_needs_update.return_value = False

        needs_update = await indexer.document_needs_update("/docs/test.md", "samehash")

        assert needs_update is False


class TestDocumentSearcher:
    @pytest.fixture
    def mock_qdrant(self):
        qdrant = AsyncMock()
        qdrant.search = AsyncMock(
            return_value=[
                {
                    "score": 0.95,
                    "payload": {
                        "chunk_id": "chunk-1",
                        "document_path": "/docs/auth.md",
                        "project_name": "my-project",
                        "heading_path": ["Authentication", "Login"],
                        "heading_level": 2,
                        "content": "The login method authenticates users.",
                        "start_line": 10,
                        "end_line": 15,
                    },
                },
                {
                    "score": 0.85,
                    "payload": {
                        "chunk_id": "chunk-2",
                        "document_path": "/docs/api.md",
                        "project_name": "my-project",
                        "heading_path": ["API", "Auth"],
                        "heading_level": 2,
                        "content": "Authentication API reference.",
                        "start_line": 20,
                        "end_line": 25,
                    },
                },
            ]
        )
        return qdrant

    @pytest.fixture
    def mock_embedder(self):
        embedder = AsyncMock()
        embedder.embed = AsyncMock(return_value=[0.1] * 1536)
        return embedder

    @pytest.fixture
    def searcher(self, mock_qdrant, mock_embedder):
        return DocumentSearcher(mock_qdrant, mock_embedder)

    @pytest.mark.asyncio
    async def test_search_returns_results(self, searcher, mock_embedder, mock_qdrant):
        results = await searcher.search("authentication login", limit=10)

        assert len(results) == 2
        assert isinstance(results[0], DocumentSearchResult)
        assert results[0].score == 0.95
        assert results[0].chunk_id == "chunk-1"
        assert results[0].document_path == "/docs/auth.md"

        mock_embedder.embed.assert_called_once_with("authentication login")
        mock_qdrant.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_project_filter(self, searcher, mock_qdrant):
        await searcher.search("login", project_name="my-project")

        call_kwargs = mock_qdrant.search.call_args[1]
        assert call_kwargs["filters"]["project_name"] == "my-project"

    @pytest.mark.asyncio
    async def test_search_with_document_type_filter(self, searcher, mock_qdrant):
        await searcher.search("login", document_type="api")

        call_kwargs = mock_qdrant.search.call_args[1]
        assert call_kwargs["filters"]["document_type"] == "api"

    @pytest.mark.asyncio
    async def test_search_with_limit(self, searcher, mock_qdrant):
        await searcher.search("login", limit=5)

        call_kwargs = mock_qdrant.search.call_args[1]
        assert call_kwargs["limit"] == 5

    @pytest.mark.asyncio
    async def test_search_no_results(self, searcher, mock_qdrant):
        mock_qdrant.search.return_value = []

        results = await searcher.search("nonexistent query")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_result_properties(self, searcher):
        results = await searcher.search("test")

        result = results[0]
        assert result.score == 0.95
        assert result.chunk_id == "chunk-1"
        assert result.document_path == "/docs/auth.md"
        assert result.project_name == "my-project"
        assert result.heading_path == ["Authentication", "Login"]
        assert result.heading_level == 2
        assert "login" in result.content.lower()
        assert result.start_line == 10
        assert result.end_line == 15

    @pytest.mark.asyncio
    async def test_find_similar_code_chunks(self, searcher, mock_qdrant, mock_embedder):
        mock_qdrant.search.return_value = [
            {
                "score": 0.9,
                "payload": {
                    "file_path": "/src/auth.py",
                    "entity_type": "function",
                    "entity_name": "login",
                    "content": "def login(email, password): ...",
                    "graph_node_id": "auth.login",
                },
            }
        ]

        results = await searcher.find_similar_code_chunks(
            doc_chunk_content="The login function authenticates users.",
            project_name="my-project",
            limit=20,
        )

        assert len(results) == 1
        mock_embedder.embed.assert_called_once()
        call_kwargs = mock_qdrant.search.call_args[1]
        assert call_kwargs["filters"]["project_name"] == "my-project"
        assert call_kwargs["limit"] == 20


class TestDocumentSearchResult:
    def test_document_search_result_creation(self):
        result = DocumentSearchResult(
            score=0.92,
            chunk_id="chunk-123",
            document_path="/docs/readme.md",
            project_name="test-project",
            heading_path=["Getting Started", "Installation"],
            heading_level=2,
            content="Install the package using pip.",
            start_line=5,
            end_line=10,
        )

        assert result.score == 0.92
        assert result.chunk_id == "chunk-123"
        assert result.document_path == "/docs/readme.md"
        assert result.project_name == "test-project"
        assert "Installation" in result.heading_path
        assert result.heading_level == 2
