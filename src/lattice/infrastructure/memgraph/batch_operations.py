"""Batch flush operations for graph entities and relationships."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from lattice.infrastructure.memgraph.buffers import EntityBuffer, RelationshipBuffer
from lattice.infrastructure.memgraph.queries import BatchQueries

if TYPE_CHECKING:
    from lattice.infrastructure.memgraph.client import MemgraphClient

logger = logging.getLogger(__name__)


async def flush_entities(
    client: MemgraphClient,
    buffer: EntityBuffer,
    stats: dict[str, int],
) -> None:
    """Flush all buffered entities to the graph database."""
    if buffer.files:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_FILE, buffer.files)
            stats["nodes_created"] += len(buffer.files)
        except Exception as e:
            logger.warning(f"Failed to flush files: {e}")
        buffer.files.clear()

    if buffer.classes:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_CLASS, buffer.classes)
            stats["nodes_created"] += len(buffer.classes)
        except Exception as e:
            logger.warning(f"Failed to flush classes: {e}")
        buffer.classes.clear()

    if buffer.functions:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_FUNCTION, buffer.functions)
            stats["nodes_created"] += len(buffer.functions)
        except Exception as e:
            logger.warning(f"Failed to flush functions: {e}")
        buffer.functions.clear()

    if buffer.methods:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_METHOD, buffer.methods)
            stats["nodes_created"] += len(buffer.methods)
        except Exception as e:
            logger.warning(f"Failed to flush methods: {e}")
        buffer.methods.clear()

    if buffer.imports:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_IMPORT, buffer.imports)
            stats["nodes_created"] += len(buffer.imports)
        except Exception as e:
            logger.warning(f"Failed to flush imports: {e}")
        buffer.imports.clear()


async def flush_relationships(
    client: MemgraphClient,
    buffer: RelationshipBuffer,
    stats: dict[str, int],
) -> None:
    """Flush all buffered relationships to the graph database."""
    if buffer.defines_class:
        try:
            await client.execute_batch(
                BatchQueries.BATCH_CREATE_DEFINES_CLASS, buffer.defines_class
            )
            stats["relationships_created"] += len(buffer.defines_class)
        except Exception as e:
            logger.warning(f"Failed to flush defines_class: {e}")
        buffer.defines_class.clear()

    if buffer.defines_function:
        try:
            await client.execute_batch(
                BatchQueries.BATCH_CREATE_DEFINES_FUNCTION, buffer.defines_function
            )
            stats["relationships_created"] += len(buffer.defines_function)
        except Exception as e:
            logger.warning(f"Failed to flush defines_function: {e}")
        buffer.defines_function.clear()

    if buffer.defines_method:
        try:
            await client.execute_batch(
                BatchQueries.BATCH_CREATE_DEFINES_METHOD, buffer.defines_method
            )
            stats["relationships_created"] += len(buffer.defines_method)
        except Exception as e:
            logger.warning(f"Failed to flush defines_method: {e}")
        buffer.defines_method.clear()

    if buffer.extends:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_EXTENDS, buffer.extends)
            stats["relationships_created"] += len(buffer.extends)
        except Exception as e:
            logger.warning(f"Failed to flush extends: {e}")
        buffer.extends.clear()

    if buffer.imports:
        try:
            await client.execute_batch(BatchQueries.BATCH_CREATE_IMPORTS, buffer.imports)
            stats["relationships_created"] += len(buffer.imports)
        except Exception as e:
            logger.warning(f"Failed to flush imports: {e}")
        buffer.imports.clear()

    if buffer.calls:
        try:
            results = await client.execute_batch(BatchQueries.BATCH_CREATE_CALLS, buffer.calls)
            created = sum(r.get("created", 0) for r in results) if results else 0
            stats["relationships_created"] += created
            if created < len(buffer.calls):
                failed = len(buffer.calls) - created
                logger.debug(f"CALLS: {created} created, {failed} unresolved")
        except Exception as e:
            logger.warning(f"Failed to flush calls: {e}")
        buffer.calls.clear()


async def flush_all(
    client: MemgraphClient,
    entity_buffer: EntityBuffer,
    relationship_buffer: RelationshipBuffer,
    stats: dict[str, int],
) -> None:
    """Flush all pending entity and relationship writes."""
    logger.info("Flushing all pending graph writes...")
    await flush_entities(client, entity_buffer, stats)
    await flush_relationships(client, relationship_buffer, stats)
    logger.info(
        f"Flush complete: {stats['nodes_created']} nodes, "
        f"{stats['relationships_created']} relationships"
    )
