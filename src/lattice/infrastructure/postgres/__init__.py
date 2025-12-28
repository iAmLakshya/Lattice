"""PostgreSQL database adapter."""

from lattice.infrastructure.postgres.api import PostgresClient, create_postgres_client

__all__ = ["PostgresClient", "create_postgres_client"]
