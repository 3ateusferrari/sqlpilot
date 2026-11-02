"""Database schema introspection, DDL formatting, sample data extraction and sensitive masking."""

import re
import time
from typing import Any

from psycopg import AsyncConnection, sql
from psycopg_pool import AsyncConnectionPool

from app.db.session import get_readonly_pool
from app.logging import get_logger

logger = get_logger(__name__)

SENSITIVE_FIELD_PATTERNS = (
    "email",
    "phone",
    "fax",
    "address",
    "postal_code",
    "password",
    "secret",
    "token",
    "ssn",
    "cpf",
    "card",
)


def is_sensitive_column(column_name: str) -> bool:
    """Return True if the column name matches sensitive data heuristics."""
    col_lower = column_name.lower()
    return any(pattern in col_lower for pattern in SENSITIVE_FIELD_PATTERNS)


def mask_sensitive_value(column_name: str, value: Any) -> Any:
    """Mask sensitive string values and sanitize comment breakouts."""
    if value is None:
        return None

    # Sanitize newline breaks and block comment terminators for string values
    if isinstance(value, str):
        value = value.replace("\n", " ").replace("\r", " ").replace("*/", "* /")

    if not is_sensitive_column(column_name):
        return value

    val_str = str(value).strip()
    if not val_str:
        return val_str

    col_lower = column_name.lower()

    if "email" in col_lower:
        if "@" in val_str:
            user, domain = val_str.split("@", 1)
            first_char = user[0] if user else ""
            return f"{first_char}***@{domain}"
        return "***"

    if "phone" in col_lower or "fax" in col_lower:
        # Match standard phone formats e.g., +1 (780) 428-9482 or +55 11 9999-1234
        m = re.match(r"^(\+\d{1,3}\s*)?\(?\d{2,4}\)?[\s\-]*\d{3,4}[\s\-]*(\d{4})$", val_str)
        if m:
            prefix = m.group(1).strip() if m.group(1) else ""
            suffix = m.group(2)
            if prefix:
                return f"{prefix} (***) ***-{suffix}"
            return f"(***) ***-{suffix}"
        if len(val_str) > 6:
            return f"{val_str[:3]}***{val_str[-4:]}"
        return "***"

    if "postal_code" in col_lower:
        if len(val_str) > 2:
            return f"{val_str[:2]}***"
        return "***"

    if "address" in col_lower:
        words = val_str.split()
        if words:
            return f"{words[0]} ***"
        return "***"

    return "***"


class SchemaLoader:
    """Introspects PostgreSQL schema, extracts DDL, PKs, FKs and masked sample rows."""

    def __init__(
        self,
        pool: AsyncConnectionPool | None = None,
        ttl_seconds: float = 3600.0,
    ) -> None:
        self._pool = pool
        self._ttl_seconds = ttl_seconds
        self._cached_valid_tables: list[str] | None = None
        self._tables_cache_timestamp: float | None = None
        self._cached_schema: tuple[list[str], str] | None = None
        self._schema_cache_timestamp: float | None = None

    def _get_pool(self) -> AsyncConnectionPool:
        """Return the assigned pool or the global readonly pool."""
        return self._pool if self._pool is not None else get_readonly_pool()

    def _is_tables_cache_valid(self) -> bool:
        """Check if cached valid tables list has not expired."""
        if self._cached_valid_tables is None or self._tables_cache_timestamp is None:
            return False
        return (time.monotonic() - self._tables_cache_timestamp) < self._ttl_seconds

    def _is_schema_cache_valid(self) -> bool:
        """Check if cached schema has not expired."""
        if self._cached_schema is None or self._schema_cache_timestamp is None:
            return False
        return (time.monotonic() - self._schema_cache_timestamp) < self._ttl_seconds

    def clear_cache(self) -> None:
        """Invalidate in-memory schema and tables cache."""
        self._cached_valid_tables = None
        self._tables_cache_timestamp = None
        self._cached_schema = None
        self._schema_cache_timestamp = None

    async def _fetch_valid_tables(self, conn: AsyncConnection[Any]) -> list[str]:
        """Query information_schema for base tables in public schema using given connection."""
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name;
                """
            )
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def get_valid_tables(
        self,
        use_cache: bool = True,
        conn: AsyncConnection[Any] | None = None,
    ) -> list[str]:
        """Return an ordered list of base tables in the public schema."""
        if use_cache and self._is_tables_cache_valid():
            assert self._cached_valid_tables is not None
            return self._cached_valid_tables

        if conn is not None:
            tables = await self._fetch_valid_tables(conn)
        else:
            pool = self._get_pool()
            async with pool.connection() as c:
                tables = await self._fetch_valid_tables(c)

        self._cached_valid_tables = tables
        self._tables_cache_timestamp = time.monotonic()
        return tables

    async def load_schema(self, use_cache: bool = True) -> tuple[list[str], str]:
        """Extract DDL schema, foreign key relations, and masked sample data.

        Returns:
            A tuple of (valid_tables_list, schema_context_string).
        """
        if use_cache and self._is_schema_cache_valid():
            assert self._cached_schema is not None
            return self._cached_schema

        pool = self._get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Fetch valid tables reusing current connection to prevent pool starvation
                tables = await self.get_valid_tables(use_cache=False, conn=conn)

                # 2. Fetch column definitions
                await cur.execute(
                    """
                    SELECT table_name, column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position;
                    """
                )
                columns_by_table: dict[str, list[tuple[str, str, str]]] = {}
                for tbl, col, dt, nullable in await cur.fetchall():
                    columns_by_table.setdefault(tbl, []).append((col, dt, nullable))

                # 3. Fetch primary keys from pg_constraint
                await cur.execute(
                    """
                    SELECT
                        c.relname AS table_name,
                        a.attname AS column_name
                    FROM pg_constraint con
                    JOIN pg_class c ON c.oid = con.conrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
                    WHERE con.contype = 'p'
                      AND n.nspname = 'public'
                    ORDER BY c.relname, a.attnum;
                    """
                )
                pks_by_table: dict[str, list[str]] = {}
                for tbl, col in await cur.fetchall():
                    pks_by_table.setdefault(tbl, []).append(col)

                # 4. Fetch foreign keys from pg_constraint
                await cur.execute(
                    """
                    SELECT
                        cl.relname AS table_name,
                        att.attname AS column_name,
                        clf.relname AS foreign_table_name,
                        attf.attname AS foreign_column_name
                    FROM pg_constraint con
                    JOIN pg_class cl ON cl.oid = con.conrelid
                    JOIN pg_namespace n ON n.oid = cl.relnamespace
                    JOIN pg_class clf ON clf.oid = con.confrelid
                    JOIN LATERAL unnest(con.conkey, con.confkey) AS u(attnum, fattnum) ON true
                    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = u.attnum
                    JOIN pg_attribute attf ON attf.attrelid = con.confrelid AND attf.attnum = u.fattnum
                    WHERE con.contype = 'f'
                      AND n.nspname = 'public'
                    ORDER BY cl.relname, att.attname;
                    """
                )
                fks_by_table: dict[str, dict[str, tuple[str, str]]] = {}
                for tbl, col, ftbl, fcol in await cur.fetchall():
                    fks_by_table.setdefault(tbl, {})[col] = (ftbl, fcol)

                # 5. Build DDL and extract sample rows for each table
                table_blocks: list[str] = []
                for table in tables:
                    col_defs: list[str] = []
                    pks = pks_by_table.get(table, [])
                    fks = fks_by_table.get(table, {})
                    is_composite_pk = len(pks) > 1

                    for col_name, data_type, is_nullable in columns_by_table.get(table, []):
                        parts = [col_name, data_type]
                        if col_name in pks and not is_composite_pk:
                            parts.append("PRIMARY KEY")
                        elif is_nullable == "NO":
                            parts.append("NOT NULL")

                        if col_name in fks:
                            target_tbl, target_col = fks[col_name]
                            parts.append(f"REFERENCES {target_tbl}({target_col})")

                        col_defs.append("    " + " ".join(parts))

                    if is_composite_pk:
                        col_defs.append(f"    PRIMARY KEY ({', '.join(pks)})")

                    ddl = f"CREATE TABLE {table} (\n" + ",\n".join(col_defs) + "\n);"

                    # Fetch sample rows using sql.SQL and sql.Identifier for safe query formatting
                    sample_query = sql.SQL("SELECT * FROM {} LIMIT 3").format(sql.Identifier(table))
                    await cur.execute(sample_query)
                    if cur.description:
                        sample_cols = [desc[0] for desc in cur.description]
                        sample_rows = await cur.fetchall()
                        if sample_rows:
                            header_line = " | ".join(sample_cols)
                            rows_lines = [
                                " | ".join(
                                    str(masked_val)
                                    .replace("\n", " ")
                                    .replace("\r", " ")
                                    .replace("*/", "* /")
                                    if (masked_val := mask_sensitive_value(col, val)) is not None
                                    else "NULL"
                                    for col, val in zip(sample_cols, row, strict=True)
                                )
                                for row in sample_rows
                            ]
                            sample_block = (
                                f"/*\n3 sample rows from {table}:\n"
                                f"{header_line}\n" + "\n".join(rows_lines) + "\n*/"
                            )
                        else:
                            sample_block = f"/*\nNo sample rows from {table}\n*/"
                    else:
                        sample_block = f"/*\nNo sample rows from {table}\n*/"

                    table_blocks.append(f"{ddl}\n{sample_block}")

        schema_context = "\n\n".join(table_blocks)
        result = (tables, schema_context)

        now = time.monotonic()
        self._cached_schema = result
        self._schema_cache_timestamp = now
        self._cached_valid_tables = tables
        self._tables_cache_timestamp = now
        logger.info("schema_loaded", table_count=len(tables), ddl_length=len(schema_context))

        return result


_default_loader: SchemaLoader | None = None


def get_schema_loader() -> SchemaLoader:
    """Return the singleton SchemaLoader instance."""
    global _default_loader
    if _default_loader is None:
        _default_loader = SchemaLoader()
    return _default_loader


async def load_schema(use_cache: bool = True) -> tuple[list[str], str]:
    """Convenience helper to load database schema using the default loader."""
    return await get_schema_loader().load_schema(use_cache=use_cache)


async def get_valid_tables(use_cache: bool = True) -> list[str]:
    """Convenience helper to retrieve valid tables using the default loader."""
    return await get_schema_loader().get_valid_tables(use_cache=use_cache)
