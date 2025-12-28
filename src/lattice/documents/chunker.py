import hashlib
from uuid import UUID, uuid4

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from lattice.shared.config import get_settings
from lattice.documents.models import DocumentChunk


class DocumentChunker:
    HEADERS_TO_SPLIT = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
        ("####", "h4"),
        ("#####", "h5"),
        ("######", "h6"),
    ]

    def __init__(
        self,
        max_tokens: int | None = None,
        overlap_tokens: int | None = None,
    ):
        settings = get_settings()
        self.max_tokens = max_tokens or settings.chunk_max_tokens
        self.overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens

        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.HEADERS_TO_SPLIT,
            strip_headers=False,
        )
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_tokens * 4,
            chunk_overlap=self.overlap_tokens * 4,
            length_function=len,
        )

    def chunk_document(
        self,
        content: str,
        document_id: UUID,
        project_name: str,
    ) -> list[DocumentChunk]:
        header_splits = self._header_splitter.split_text(content)

        if not header_splits:
            return [
                DocumentChunk(
                    id=uuid4(),
                    document_id=document_id,
                    project_name=project_name,
                    content=content,
                    heading_path=[],
                    heading_level=0,
                    start_line=1,
                    end_line=content.count("\n") + 1,
                    content_hash=self._hash_content(content),
                )
            ]

        final_splits = self._text_splitter.split_documents(header_splits)

        chunks = []
        lines = content.split("\n")

        for split in final_splits:
            heading_path = self._extract_heading_path(split.metadata)
            heading_level = self._get_heading_level(split.metadata)

            start_line, end_line = self._find_line_range(lines, split.page_content)

            chunks.append(
                DocumentChunk(
                    id=uuid4(),
                    document_id=document_id,
                    project_name=project_name,
                    content=split.page_content,
                    heading_path=heading_path,
                    heading_level=heading_level,
                    start_line=start_line,
                    end_line=end_line,
                    content_hash=self._hash_content(split.page_content),
                )
            )

        return chunks

    def _extract_heading_path(self, metadata: dict) -> list[str]:
        path = []
        for key in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            if key in metadata:
                path.append(metadata[key])
        return path

    def _get_heading_level(self, metadata: dict) -> int:
        for i, key in enumerate(["h6", "h5", "h4", "h3", "h2", "h1"], 1):
            if key in metadata:
                return 7 - i
        return 0

    def _find_line_range(self, lines: list[str], content: str) -> tuple[int, int]:
        content_start = content[:100].strip()
        if not content_start:
            return 1, len(lines)

        for i, line in enumerate(lines):
            if content_start.startswith(line.strip()[:50]):
                content_lines = content.count("\n") + 1
                return i + 1, min(i + content_lines, len(lines))

        return 1, len(lines)

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()
