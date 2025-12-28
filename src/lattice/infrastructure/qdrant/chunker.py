from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from lattice.shared.config import get_settings
from lattice.shared.config.loader import ChunkingConfig
from lattice.parsing.api import CodeEntity, ParsedFile


@dataclass
class CodeChunk:
    content: str
    file_path: str
    entity_type: str
    entity_name: str
    language: str
    start_line: int
    end_line: int
    graph_node_id: str | None = None
    content_hash: str | None = None
    project_name: str | None = None

    def to_payload(self) -> dict:
        return {
            "file_path": self.file_path,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "language": self.language,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "graph_node_id": self.graph_node_id,
            "content_hash": self.content_hash,
            "project_name": self.project_name,
        }


@lru_cache(maxsize=4)
def _get_encoding(encoding_name: str = "cl100k_base") -> tiktoken.Encoding:
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    encoding = _get_encoding(encoding_name)
    return len(encoding.encode(text))


def chunk_file(
    parsed_file: ParsedFile,
    project_name: str | None = None,
    max_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[CodeChunk]:
    settings = get_settings()
    max_tokens = max_tokens or settings.chunk_max_tokens
    overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens

    chunks = []
    file_path = str(parsed_file.file_info.path)
    language = parsed_file.file_info.language.value
    content_hash = parsed_file.file_info.content_hash

    for entity in parsed_file.all_entities:
        entity_chunks = _chunk_entity(
            entity, file_path, language, content_hash, project_name,
            max_tokens, overlap_tokens
        )
        chunks.extend(entity_chunks)

    if not chunks and parsed_file.content.strip():
        file_chunks = _chunk_text(
            parsed_file.content,
            file_path,
            "file",
            parsed_file.file_info.path.name,
            language,
            1,
            content_hash,
            project_name,
            max_tokens,
            overlap_tokens,
        )
        chunks.extend(file_chunks)

    return chunks


def _chunk_entity(
    entity: CodeEntity,
    file_path: str,
    language: str,
    content_hash: str | None,
    project_name: str | None,
    max_tokens: int,
    overlap_tokens: int,
) -> list[CodeChunk]:
    entity_type = entity.type.value
    entity_name = entity.qualified_name
    content = _format_entity_content(entity)
    token_count = count_tokens(content)

    if token_count <= max_tokens:
        return [
            CodeChunk(
                content=content,
                file_path=file_path,
                entity_type=entity_type,
                entity_name=entity_name,
                language=language,
                start_line=entity.start_line,
                end_line=entity.end_line,
                graph_node_id=entity.qualified_name,
                content_hash=content_hash,
                project_name=project_name,
            )
        ]
    else:
        return _chunk_text(
            content,
            file_path,
            entity_type,
            entity_name,
            language,
            entity.start_line,
            content_hash,
            project_name,
            max_tokens,
            overlap_tokens,
        )


def _format_entity_content(entity: CodeEntity) -> str:
    content_parts = []
    if entity.signature:
        content_parts.append(entity.signature)
    if entity.docstring:
        content_parts.append(f'"""{entity.docstring}"""')
    content_parts.append(entity.code)
    return "\n".join(content_parts)


def _chunk_text(
    text: str,
    file_path: str,
    entity_type: str,
    entity_name: str,
    language: str,
    start_line: int,
    content_hash: str | None,
    project_name: str | None,
    max_tokens: int,
    overlap_tokens: int,
) -> list[CodeChunk]:
    chunk_name_separator = ChunkingConfig.chunk_name_separator
    lines = text.split("\n")
    chunks = []
    current_lines: list[str] = []
    current_tokens = 0
    chunk_start_line = start_line

    for i, line in enumerate(lines):
        line_tokens = count_tokens(line + "\n")

        if current_tokens + line_tokens > max_tokens and current_lines:
            chunk_content = "\n".join(current_lines)
            chunks.append(
                CodeChunk(
                    content=chunk_content,
                    file_path=file_path,
                    entity_type=entity_type,
                    entity_name=f"{entity_name}{chunk_name_separator}{len(chunks) + 1}",
                    language=language,
                    start_line=chunk_start_line,
                    end_line=chunk_start_line + len(current_lines) - 1,
                    graph_node_id=entity_name,
                    content_hash=content_hash,
                    project_name=project_name,
                )
            )

            overlap_lines = _calculate_overlap_lines(current_lines, overlap_tokens)
            current_lines = overlap_lines
            current_tokens = sum(count_tokens(ol + "\n") for ol in overlap_lines)
            chunk_start_line = start_line + i - len(overlap_lines)

        current_lines.append(line)
        current_tokens += line_tokens

    if current_lines:
        chunk_content = "\n".join(current_lines)
        chunk_name = entity_name
        if chunks:
            chunk_name = f"{entity_name}{chunk_name_separator}{len(chunks) + 1}"

        chunks.append(
            CodeChunk(
                content=chunk_content,
                file_path=file_path,
                entity_type=entity_type,
                entity_name=chunk_name,
                language=language,
                start_line=chunk_start_line,
                end_line=chunk_start_line + len(current_lines) - 1,
                graph_node_id=entity_name,
                content_hash=content_hash,
                project_name=project_name,
            )
        )

    return chunks


def _calculate_overlap_lines(lines: list[str], overlap_tokens: int) -> list[str]:
    overlap_lines: list[str] = []
    current_overlap_tokens = 0

    for line in reversed(lines):
        line_tokens = count_tokens(line + "\n")
        if current_overlap_tokens + line_tokens <= overlap_tokens:
            overlap_lines.insert(0, line)
            current_overlap_tokens += line_tokens
        else:
            break

    return overlap_lines
