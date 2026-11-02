"""Asynchronous connection pool manager using psycopg_pool."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


class AutoOpenAsyncConnectionPool(AsyncConnectionPool):
    """AsyncConnectionPool that opens asynchronously upon first connection acquisition."""

    async def getconn(
        self,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> AsyncConnection[Any]:
        """Obtain a connection, automatically opening the pool if not already open."""
        if not getattr(self, "_opened", False):
            await self.open()
        return await super().getconn(timeout=timeout)


_admin_pool: AutoOpenAsyncConnectionPool | None = None
_readonly_pool: AutoOpenAsyncConnectionPool | None = None


def get_admin_pool() -> AsyncConnectionPool:
    """Return the singleton admin connection pool."""
    global _admin_pool
    if _admin_pool is None or (getattr(_admin_pool, "_opened", False) and _admin_pool.closed):
        logger.info(
            "initializing_admin_pool",
            database_url=settings.database_admin_url.split("@")[-1],
        )
        _admin_pool = AutoOpenAsyncConnectionPool(
            conninfo=settings.database_admin_url,
            min_size=1,
            max_size=10,
            open=False,
            name="admin-pool",
        )
    return _admin_pool


def get_readonly_pool() -> AsyncConnectionPool:
    """Return the singleton readonly connection pool."""
    global _readonly_pool
    if _readonly_pool is None or (
        getattr(_readonly_pool, "_opened", False) and _readonly_pool.closed
    ):
        logger.info(
            "initializing_readonly_pool",
            database_url=settings.database_readonly_url.split("@")[-1],
        )
        _readonly_pool = AutoOpenAsyncConnectionPool(
            conninfo=settings.database_readonly_url,
            min_size=1,
            max_size=10,
            open=False,
            name="readonly-pool",
        )
    return _readonly_pool


async def close_pools() -> None:
    """Gracefully close all active connection pools."""
    global _admin_pool, _readonly_pool

    if _admin_pool is not None:
        if not _admin_pool.closed:
            logger.info("closing_admin_pool")
            await _admin_pool.close()
        _admin_pool = None

    if _readonly_pool is not None:
        if not _readonly_pool.closed:
            logger.info("closing_readonly_pool")
            await _readonly_pool.close()
        _readonly_pool = None


@asynccontextmanager
async def get_admin_connection() -> AsyncIterator[AsyncConnection[Any]]:
    """Context manager for acquiring an admin connection from the pool."""
    pool = get_admin_pool()
    async with pool.connection() as conn:
        yield conn


@asynccontextmanager
async def get_readonly_connection() -> AsyncIterator[AsyncConnection[Any]]:
    """Context manager for acquiring a readonly connection from the pool."""
    pool = get_readonly_pool()
    async with pool.connection() as conn:
        yield conn
