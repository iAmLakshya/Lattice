import logging
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from asyncpg import Pool, Record

from lattice.config import get_settings
from lattice.core.errors import PostgresError

logger = logging.getLogger(__name__)


class PostgresClient:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        min_pool: int | None = None,
        max_pool: int | None = None,
    ):
        settings = get_settings().postgres

        self._host = host or settings.postgres_host
        self._port = port or settings.postgres_port
        self._database = database or settings.postgres_database
        self._user = user or settings.postgres_user
        self._password = password or settings.postgres_password.get_secret_value()
        self._min_pool = min_pool or settings.postgres_pool_min
        self._max_pool = max_pool or settings.postgres_pool_max

        self._pool: Pool | None = None

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        try:
            self._pool = await asyncpg.create_pool(
                host=self._host,
                port=self._port,
                database=self._database,
                user=self._user,
                password=self._password,
                min_size=self._min_pool,
                max_size=self._max_pool,
            )
            logger.info(f"Connected to PostgreSQL at {self._host}:{self._port}/{self._database}")
        except Exception as e:
            raise PostgresError(
                f"Failed to connect to PostgreSQL at {self._host}:{self._port}: {e}",
                cause=e,
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        if self._pool is None:
            await self.connect()

        async with self._pool.acquire() as conn:
            yield conn

    async def execute(self, query: str, *args: Any) -> str:
        if self._pool is None:
            await self.connect()

        try:
            async with self._pool.acquire() as conn:
                return await conn.execute(query, *args)
        except Exception as e:
            raise PostgresError(f"Query execution failed: {e}", cause=e)

    async def fetch(self, query: str, *args: Any) -> list[Record]:
        if self._pool is None:
            await self.connect()

        try:
            async with self._pool.acquire() as conn:
                return await conn.fetch(query, *args)
        except Exception as e:
            raise PostgresError(f"Query fetch failed: {e}", cause=e)

    async def fetchrow(self, query: str, *args: Any) -> Record | None:
        if self._pool is None:
            await self.connect()

        try:
            async with self._pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        except Exception as e:
            raise PostgresError(f"Query fetchrow failed: {e}", cause=e)

    async def fetchval(self, query: str, *args: Any) -> Any:
        if self._pool is None:
            await self.connect()

        try:
            async with self._pool.acquire() as conn:
                return await conn.fetchval(query, *args)
        except Exception as e:
            raise PostgresError(f"Query fetchval failed: {e}", cause=e)

    async def __aenter__(self) -> "PostgresClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
