import logging
from collections.abc import Callable, Sequence

from lattice.shared.config import get_settings
from lattice.infrastructure.llm import BaseEmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


def create_embedder(
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_concurrent: int | None = None,
) -> BaseEmbeddingProvider:
    settings = get_settings()
    max_concurrent = max_concurrent or settings.max_concurrent_requests

    embedding_provider = get_embedding_provider(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
    embedding_provider.set_concurrency(max_concurrent)

    logger.info(
        f"Created embedder with {embedding_provider.config.provider}/"
        f"{embedding_provider.config.model}"
    )

    return embedding_provider


async def embed_with_progress(
    provider: BaseEmbeddingProvider,
    texts: Sequence[str],
    batch_size: int = 100,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    all_embeddings = []
    texts_list = list(texts)
    total = len(texts_list)

    for i in range(0, total, batch_size):
        batch = texts_list[i : i + batch_size]
        embeddings = await provider.embed_batch(batch, batch_size=len(batch))
        all_embeddings.extend(embeddings)

        if progress_callback:
            progress_callback(min(i + batch_size, total), total)

    logger.info(
        f"Generated {len(all_embeddings)} embeddings across "
        f"{(total + batch_size - 1) // batch_size} batches"
    )
    return all_embeddings
