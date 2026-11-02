"""Asynchronous connection pool manager using psycopg_pool."""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg_pool import AsyncConnectionPool

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)


def _mask_database_url(url: str) -> str:
    """Mask password credentials in database URL or conninfo string safely."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme and parsed.netloc:
            if parsed.password:
                netloc = f"{parsed.username or ''}:***@{parsed.hostname or ''}"
                if parsed.port:
                    netloc += f":{parsed.port}"
                return urlunsplit(
                    (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
                )
            return url
        d = conninfo_to_dict(url)
        if "password" in d:
            d["password"] = "***"
        return make_conninfo("", **d)
    except Exception:
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


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
            database_url=_mask_database_url(settings.database_admin_url),
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
            database_url=_mask_database_url(settings.database_readonly_url),
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
    """Gracefully close all active connection pools, ensuring isolation on error."""
    global _admin_pool, _readonly_pool

    admin, readonly = _admin_pool, _readonly_pool
    _admin_pool, _readonly_pool = None, None

    tasks = []
    if admin is not None and not admin.closed:
        logger.info("closing_admin_pool")
        tasks.append(admin.close())

    if readonly is not None and not readonly.closed:
        logger.info("closing_readonly_pool")
        tasks.append(readonly.close())

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, BaseException):
                logger.error("error_closing_pool", error=str(res))


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
