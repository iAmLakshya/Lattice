import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from lattice.documents.models import DocumentInfo


@dataclass
class DocumentScanStatistics:
    file_count: int
    total_lines: int
    total_size: int


class DocumentScanner:
    DEFAULT_EXTENSIONS = {".md", ".markdown", ".mdx"}
    DEFAULT_IGNORE = ["node_modules", ".git", ".venv", "dist", "build", "__pycache__"]

    def __init__(
        self,
        root_path: str | Path,
        extensions: set[str] | None = None,
        ignore_patterns: list[str] | None = None,
    ):
        self.root_path = Path(root_path).resolve()
        self.extensions = extensions or self.DEFAULT_EXTENSIONS
        self.ignore_patterns = ignore_patterns or self.DEFAULT_IGNORE

        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")

    def _should_ignore(self, path: Path) -> bool:
        for pattern in self.ignore_patterns:
            for part in path.parts:
                if fnmatch(part, pattern):
                    return True
        return False

    def _compute_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def scan(self) -> Iterator[DocumentInfo]:
        if self.root_path.is_file():
            ext = self.root_path.suffix.lower()
            if ext in self.extensions:
                try:
                    content = self.root_path.read_bytes()
                    yield DocumentInfo(
                        path=self.root_path,
                        relative_path=self.root_path.name,
                        content_hash=self._compute_hash(content),
                        size_bytes=len(content),
                        line_count=content.count(b"\n") + 1,
                    )
                except (OSError, PermissionError):
                    pass
            return

        for file_path in self.root_path.rglob("*"):
            if file_path.is_dir():
                continue

            relative = file_path.relative_to(self.root_path)
            if self._should_ignore(relative):
                continue

            ext = file_path.suffix.lower()
            if ext not in self.extensions:
                continue

            try:
                content = file_path.read_bytes()
                yield DocumentInfo(
                    path=file_path,
                    relative_path=str(relative),
                    content_hash=self._compute_hash(content),
                    size_bytes=len(content),
                    line_count=content.count(b"\n") + 1,
                )
            except (OSError, PermissionError):
                continue

    def scan_all(self) -> list[DocumentInfo]:
        return list(self.scan())

    def get_statistics(self) -> DocumentScanStatistics:
        file_count = 0
        total_lines = 0
        total_size = 0

        for doc_info in self.scan():
            file_count += 1
            total_lines += doc_info.line_count
            total_size += doc_info.size_bytes

        return DocumentScanStatistics(
            file_count=file_count,
            total_lines=total_lines,
            total_size=total_size,
        )
