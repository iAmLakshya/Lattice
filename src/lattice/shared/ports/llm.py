from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(
        self, texts: Sequence[str], batch_size: int = 100
    ) -> list[list[float]]: ...
