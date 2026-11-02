"""Integration tests for database security and role permissions."""

import json
import uuid

import psycopg
import pytest
from psycopg import errors

from app.config import settings


@pytest.mark.asyncio
async def test_readonly_user_can_select_customer() -> None:
    """Validate that sqlpilot_readonly can SELECT from customer and count > 0."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT count(*) FROM customer")
            row = await cur.fetchone()
            assert row is not None
            count = row[0]
            assert count > 0


@pytest.mark.asyncio
async def test_readonly_user_cannot_insert_artist() -> None:
    """Validate that sqlpilot_readonly cannot INSERT into artist."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            with pytest.raises((errors.ReadOnlySqlTransaction, errors.InsufficientPrivilege)):
                await cur.execute("INSERT INTO artist (name) VALUES ('Hacker Band')")


@pytest.mark.asyncio
async def test_readonly_user_cannot_update_customer() -> None:
    """Validate that sqlpilot_readonly cannot UPDATE customer."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            with pytest.raises((errors.ReadOnlySqlTransaction, errors.InsufficientPrivilege)):
                await cur.execute("UPDATE customer SET first_name = 'Hacked' WHERE customer_id = 1")


@pytest.mark.asyncio
async def test_readonly_user_cannot_delete_invoice() -> None:
    """Validate that sqlpilot_readonly cannot DELETE from invoice."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            with pytest.raises((errors.ReadOnlySqlTransaction, errors.InsufficientPrivilege)):
                await cur.execute("DELETE FROM invoice WHERE invoice_id = 1")


@pytest.mark.asyncio
async def test_readonly_user_cannot_drop_table() -> None:
    """Validate that sqlpilot_readonly cannot DROP table."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            with pytest.raises((errors.ReadOnlySqlTransaction, errors.InsufficientPrivilege)):
                await cur.execute("DROP TABLE album")


@pytest.mark.asyncio
async def test_readonly_user_statement_timeout() -> None:
    """Validate that queries longer than 5 seconds are canceled due to statement_timeout."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            with pytest.raises(errors.QueryCanceled):
                await cur.execute("SELECT pg_sleep(6)")


@pytest.mark.asyncio
async def test_readonly_user_cannot_access_internal_schema() -> None:
    """Validate that sqlpilot_readonly cannot access internal.audit_logs schema."""
    async with await psycopg.AsyncConnection.connect(settings.database_readonly_url) as conn:
        async with conn.cursor() as cur:
            with pytest.raises(errors.InsufficientPrivilege):
                await cur.execute("SELECT * FROM internal.audit_logs")


@pytest.mark.asyncio
async def test_admin_can_insert_and_query_audit_logs() -> None:
    """Validate that admin user can write and query internal.audit_logs with cleanup."""
    test_thread_id = f"test-thread-{uuid.uuid4()}"
    async with await psycopg.AsyncConnection.connect(settings.database_admin_url) as conn:
        async with conn.cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO internal.audit_logs (
                        thread_id,
                        pergunta,
                        sql_original,
                        nivel_risco,
                        motivos_risco,
                        acao_humana,
                        sql_final,
                        feedback,
                        revisor
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id, thread_id, nivel_risco, motivos_risco, revisor;
                    """,
                    (
                        test_thread_id,
                        "Quais clientes gastaram mais de 50 dólares?",
                        "SELECT * FROM customer WHERE id IN (SELECT customer_id FROM invoice)",
                        "high",
                        json.dumps(
                            [
                                "EXPLAIN cost exceeds threshold",
                                "Access to sensitive customer table",
                            ]
                        ),
                        "approve",
                        "SELECT customer_id, sum(total) FROM invoice GROUP BY customer_id HAVING sum(total) > 50",
                        "Aprovado com query agrupada otimizada",
                        "admin_user",
                    ),
                )
                inserted = await cur.fetchone()
                assert inserted is not None
                assert inserted[1] == test_thread_id
                assert inserted[2] == "high"
                assert inserted[4] == "admin_user"

                # Verify select
                await cur.execute(
                    "SELECT count(*) FROM internal.audit_logs WHERE thread_id = %s",
                    (test_thread_id,),
                )
                count_row = await cur.fetchone()
                assert count_row is not None
                assert count_row[0] == 1
            finally:
                await cur.execute(
                    "DELETE FROM internal.audit_logs WHERE thread_id = %s",
                    (test_thread_id,),
                )
