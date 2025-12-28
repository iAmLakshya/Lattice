from __future__ import annotations

from typing import Any, Protocol


class VectorReader(Protocol):
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...

    async def health_check(self) -> bool: ...


class VectorWriter(Protocol):
    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None: ...

    async def delete(self, collection: str, filters: dict[str, Any]) -> None: ...
