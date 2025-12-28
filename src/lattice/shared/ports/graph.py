from __future__ import annotations

from typing import Any, Protocol


class GraphReader(Protocol):
    async def execute(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...

    async def health_check(self) -> bool: ...

    async def get_node_count(self) -> int: ...

    async def get_relationship_count(self) -> int: ...


class GraphWriter(Protocol):
    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...

    async def execute_batch_write(
        self, query: str, batch: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    async def clear_database(self) -> None: ...
