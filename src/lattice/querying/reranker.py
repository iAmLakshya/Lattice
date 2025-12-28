from dataclasses import dataclass
from typing import Any

from lattice.shared.config.loader import RerankerConfig
from lattice.shared.types import ResultSource


@dataclass
class SearchResult:
    source: str
    score: float
    file_path: str
    entity_type: str
    entity_name: str
    content: str | None = None
    summary: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    graph_node_id: str | None = None
    metadata: dict[str, Any] | None = None

    def get_key(self) -> str:
        return f"{self.file_path}:{self.entity_name}:{self.start_line}"


def normalize_scores(results: list[SearchResult]) -> list[SearchResult]:
    if not results:
        return results

    max_score = max(r.score for r in results)
    min_score = min(r.score for r in results)
    score_range = max_score - min_score

    if score_range == 0:
        return [
            SearchResult(
                source=r.source,
                score=1.0,
                file_path=r.file_path,
                entity_type=r.entity_type,
                entity_name=r.entity_name,
                content=r.content,
                summary=r.summary,
                start_line=r.start_line,
                end_line=r.end_line,
                graph_node_id=r.graph_node_id,
                metadata=r.metadata,
            )
            for r in results
        ]

    return [
        SearchResult(
            source=r.source,
            score=(r.score - min_score) / score_range,
            file_path=r.file_path,
            entity_type=r.entity_type,
            entity_name=r.entity_name,
            content=r.content,
            summary=r.summary,
            start_line=r.start_line,
            end_line=r.end_line,
            graph_node_id=r.graph_node_id,
            metadata=r.metadata,
        )
        for r in results
    ]


def fuse_results(
    graph_results: list[dict],
    vector_results: list[dict],
    graph_weight: float | None = None,
    vector_weight: float | None = None,
) -> list[SearchResult]:
    if graph_weight is None:
        graph_weight = RerankerConfig.graph_weight
    if vector_weight is None:
        vector_weight = RerankerConfig.vector_weight

    results_map: dict[str, SearchResult] = {}

    for r in graph_results:
        result = _create_graph_result(r, graph_weight)
        results_map[result.get_key()] = result

    for r in vector_results:
        result = _create_vector_result(r, vector_weight)
        key = result.get_key()

        if key in results_map:
            existing = results_map[key]
            results_map[key] = SearchResult(
                source=ResultSource.HYBRID.value,
                score=existing.score + result.score,
                file_path=existing.file_path,
                entity_type=existing.entity_type,
                entity_name=existing.entity_name,
                content=result.content or existing.content,
                summary=existing.summary or result.summary,
                start_line=existing.start_line,
                end_line=existing.end_line,
                graph_node_id=existing.graph_node_id,
                metadata=existing.metadata,
            )
        else:
            results_map[key] = result

    results = list(results_map.values())
    results.sort(key=lambda r: r.score, reverse=True)

    return results


def deduplicate_results(
    results: list[SearchResult],
    max_per_file: int | None = None,
) -> list[SearchResult]:
    if max_per_file is None:
        max_per_file = RerankerConfig.max_results_per_file

    seen_keys: set[str] = set()
    file_counts: dict[str, int] = {}
    deduplicated: list[SearchResult] = []

    for result in results:
        key = result.get_key()

        if key in seen_keys:
            continue

        file_count = file_counts.get(result.file_path, 0)
        if file_count >= max_per_file:
            continue

        seen_keys.add(key)
        file_counts[result.file_path] = file_count + 1
        deduplicated.append(result)

    return deduplicated


def _create_graph_result(r: dict, graph_weight: float) -> SearchResult:
    return SearchResult(
        source=ResultSource.GRAPH.value,
        score=graph_weight,
        file_path=r.get("file_path", ""),
        entity_type=r.get("type", r.get("entity_type", "")),
        entity_name=r.get("name", r.get("entity_name", "")),
        summary=r.get("summary"),
        start_line=r.get("start_line"),
        end_line=r.get("end_line"),
        graph_node_id=r.get("qualified_name"),
    )


def _create_vector_result(r: dict, vector_weight: float) -> SearchResult:
    return SearchResult(
        source=ResultSource.VECTOR.value,
        score=r.get("score", 0) * vector_weight,
        file_path=r.get("file_path", ""),
        entity_type=r.get("entity_type", ""),
        entity_name=r.get("entity_name", ""),
        content=r.get("content"),
        summary=r.get("summary"),
        start_line=r.get("start_line"),
        end_line=r.get("end_line"),
        graph_node_id=r.get("graph_node_id"),
    )
