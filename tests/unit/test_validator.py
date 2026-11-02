"""Unit tests for AST SQL validator."""

import pytest
from sqlglot import exp

from app.security import (
    ALLOWED_SCHEMAS,
    FORBIDDEN_EXPRESSIONS,
    FORBIDDEN_FUNCTIONS,
    FORBIDDEN_SCHEMAS,
    ValidationResult,
    validate_and_transform_sql,
)

VALID_TABLES = {
    "album",
    "artist",
    "customer",
    "employee",
    "genre",
    "invoice",
    "invoice_line",
    "media_type",
    "playlist",
    "playlist_track",
    "track",
}


def test_exports_and_constants() -> None:
    """Validate that security constants and models are properly exported."""
    assert issubclass(ValidationResult, object)
    assert callable(validate_and_transform_sql)

    # Sleep functions
    assert "pg_sleep" in FORBIDDEN_FUNCTIONS
    assert "pg_sleep_for" in FORBIDDEN_FUNCTIONS
    assert "pg_sleep_until" in FORBIDDEN_FUNCTIONS

    # Backend admin functions
    assert "pg_terminate_backend" in FORBIDDEN_FUNCTIONS
    assert "pg_cancel_backend" in FORBIDDEN_FUNCTIONS

    # File functions
    assert "pg_read_file" in FORBIDDEN_FUNCTIONS
    assert "pg_write_file" in FORBIDDEN_FUNCTIONS
    assert "pg_read_binary_file" in FORBIDDEN_FUNCTIONS
    assert "pg_ls_dir" in FORBIDDEN_FUNCTIONS
    assert "pg_stat_file" in FORBIDDEN_FUNCTIONS

    # dblink
    assert "dblink" in FORBIDDEN_FUNCTIONS
    assert "dblink_exec" in FORBIDDEN_FUNCTIONS

    # Large objects
    assert "lo_import" in FORBIDDEN_FUNCTIONS
    assert "lo_export" in FORBIDDEN_FUNCTIONS
    assert "lo_get" in FORBIDDEN_FUNCTIONS
    assert "lo_put" in FORBIDDEN_FUNCTIONS
    assert "lo_unlink" in FORBIDDEN_FUNCTIONS

    # Config and XML
    assert "set_config" in FORBIDDEN_FUNCTIONS
    assert "current_setting" in FORBIDDEN_FUNCTIONS
    assert "query_to_xml" in FORBIDDEN_FUNCTIONS

    # Expressions
    assert exp.Insert in FORBIDDEN_EXPRESSIONS
    assert exp.Update in FORBIDDEN_EXPRESSIONS
    assert exp.Delete in FORBIDDEN_EXPRESSIONS
    assert exp.Drop in FORBIDDEN_EXPRESSIONS
    assert exp.Alter in FORBIDDEN_EXPRESSIONS
    assert exp.Command in FORBIDDEN_EXPRESSIONS
    assert exp.Transaction in FORBIDDEN_EXPRESSIONS
    assert exp.Into in FORBIDDEN_EXPRESSIONS

    # Schemas
    assert "" in ALLOWED_SCHEMAS
    assert "public" in ALLOWED_SCHEMAS
    assert "pg_catalog" in FORBIDDEN_SCHEMAS
    assert "information_schema" in FORBIDDEN_SCHEMAS
    assert "internal" in FORBIDDEN_SCHEMAS


def test_valid_simple_query() -> None:
    """Simple SELECT on valid table should pass."""
    sql = "SELECT * FROM artist"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is True
    assert result.errors == []
    assert result.tables_referenced == ["artist"]
    assert result.transformed_sql is not None
    assert "artist" in result.transformed_sql.lower()


def test_valid_joins_query() -> None:
    """SELECT with multiple JOINs on valid tables should pass."""
    sql = """
        SELECT ar.name, al.title, tr.name AS track_name
        FROM artist ar
        JOIN album al ON ar.artist_id = al.artist_id
        JOIN track tr ON al.album_id = tr.album_id
    """
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is True
    assert result.errors == []
    assert result.tables_referenced == ["album", "artist", "track"]
    assert result.transformed_sql is not None


def test_valid_cte_query() -> None:
    """CTEs should be parsed without confusing CTE aliases with physical tables."""
    sql = """
        WITH top_artists AS (
            SELECT artist_id, COUNT(*) AS album_count
            FROM album
            GROUP BY artist_id
        )
        SELECT * FROM top_artists
    """
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is True
    assert result.errors == []
    # top_artists is a CTE alias, only album is a physical table
    assert result.tables_referenced == ["album"]
    assert result.transformed_sql is not None


def test_valid_subquery() -> None:
    """Subqueries on valid tables should pass and collect physical tables."""
    sql = "SELECT * FROM album WHERE artist_id IN (SELECT artist_id FROM artist)"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is True
    assert result.errors == []
    assert result.tables_referenced == ["album", "artist"]
    assert result.transformed_sql is not None


def test_valid_union_query() -> None:
    """UNION of SELECTs should pass and collect physical tables."""
    sql = "SELECT name FROM artist UNION SELECT title FROM album"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is True
    assert result.errors == []
    assert result.tables_referenced == ["album", "artist"]
    assert result.transformed_sql is not None


def test_valid_query_without_tables() -> None:
    """Queries without FROM clause (e.g., SELECT 1) should pass."""
    sql = "SELECT 1 AS num"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is True
    assert result.errors == []
    assert result.tables_referenced == []
    assert result.transformed_sql is not None


def test_block_multiple_statements() -> None:
    """Queries with multiple statements must be rejected."""
    sql = "SELECT 1; DROP TABLE artist;"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert any("múltiplos" in err.lower() or "multiple" in err.lower() for err in result.errors)
    assert result.transformed_sql is None


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO artist (artist_id, name) VALUES (999, 'Test')",
        "UPDATE artist SET name = 'Test' WHERE artist_id = 1",
        "DELETE FROM artist WHERE artist_id = 1",
        "DROP TABLE artist",
        "ALTER TABLE artist ADD COLUMN dummy int",
        "TRUNCATE TABLE artist",
        "CREATE TABLE test (id int)",
        "GRANT ALL ON artist TO public",
        "REVOKE ALL ON artist FROM public",
        "COPY artist TO '/tmp/artist.csv'",
    ],
)
def test_block_mutations(sql: str) -> None:
    """All DDL/DML mutation statements must be rejected."""
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.transformed_sql is None


def test_block_select_into() -> None:
    """SELECT ... INTO ... statements must be rejected."""
    sql = "SELECT * INTO new_table FROM artist"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert any("into" in err.lower() for err in result.errors)
    assert result.transformed_sql is None


def test_block_mutation_inside_cte() -> None:
    """Data-modifying CTEs must be blocked."""
    sql = """
        WITH evil AS (
            DELETE FROM artist WHERE artist_id = 1 RETURNING artist_id
        )
        SELECT * FROM evil
    """
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.transformed_sql is None


def test_block_cte_shadowing_bypass() -> None:
    """CTEs shadowing forbidden or unknown tables must not bypass security checks."""
    # Attempting to access forbidden schema/table internal.audit_logs via CTE alias
    sql1 = "WITH audit_logs AS (SELECT * FROM internal.audit_logs) SELECT * FROM audit_logs"
    res1 = validate_and_transform_sql(sql1, valid_tables=VALID_TABLES)
    assert res1.is_valid is False
    assert any("internal" in err.lower() or "audit_logs" in err.lower() for err in res1.errors)

    # Attempting to access unknown table pg_tables via CTE alias
    sql2 = "WITH pg_tables AS (SELECT * FROM pg_tables) SELECT * FROM pg_tables"
    res2 = validate_and_transform_sql(sql2, valid_tables=VALID_TABLES)
    assert res2.is_valid is False
    assert any("pg_tables" in err.lower() for err in res2.errors)


@pytest.mark.parametrize(
    "func_call",
    [
        "pg_sleep(5)",
        "pg_sleep_for('5 seconds')",
        "pg_sleep_until('2026-11-03')",
        "pg_terminate_backend(1234)",
        "pg_cancel_backend(1234)",
        "pg_read_file('/etc/passwd')",
        "pg_write_file('/tmp/test', 'pwn')",
        "pg_read_binary_file('/etc/shadow')",
        "pg_ls_dir('/tmp')",
        "pg_stat_file('/etc/passwd')",
        "dblink('host=remote', 'SELECT 1')",
        "dblink_exec('host=remote', 'DROP TABLE artist')",
        "lo_import('/etc/passwd')",
        "lo_export(1, '/tmp/leak')",
        "lo_get(1)",
        "lo_put(1, 0, 'data')",
        "lo_unlink(1)",
        "set_config('role', 'admin', false)",
        "current_setting('app.token')",
        "query_to_xml('SELECT * FROM artist', true, false, '')",
    ],
)
def test_block_forbidden_functions(func_call: str) -> None:
    """Forbidden functions must be rejected."""
    sql = f"SELECT {func_call}"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert any("proibida" in err.lower() or "forbidden" in err.lower() for err in result.errors)
    assert result.transformed_sql is None


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM internal.audit_logs",
    ],
)
def test_block_forbidden_schemas(sql: str) -> None:
    """Queries referencing forbidden schemas must be rejected."""
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.transformed_sql is None


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM secret.artist",
        "SELECT * FROM mydb.artist",
        "SELECT * FROM custom_schema.track",
    ],
)
def test_block_unauthorized_schemas(sql: str) -> None:
    """Schemas other than public or empty must be rejected."""
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert any("schema" in err.lower() for err in result.errors)
    assert result.transformed_sql is None


def test_block_unknown_table() -> None:
    """Tables outside the valid_tables whitelist must be rejected."""
    sql = "SELECT * FROM tabela_fantasma"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert any("tabela_fantasma" in err for err in result.errors)
    assert result.transformed_sql is None
    assert "tabela_fantasma" in result.tables_referenced


def test_block_raw_syntax_error() -> None:
    """Raw unrecoverable syntax errors must be caught and reported as errors."""
    sql = "SELECT FROM WHERE ;;;"
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert any("sintaxe" in err.lower() or "syntax" in err.lower() for err in result.errors)
    assert result.transformed_sql is None


@pytest.mark.parametrize("sql", ["", "   ", ";", ";;;"])
def test_block_empty_or_whitespace(sql: str) -> None:
    """Empty queries or whitespace must be rejected."""
    result = validate_and_transform_sql(sql, valid_tables=VALID_TABLES)

    assert result.is_valid is False
    assert len(result.errors) > 0
    assert result.transformed_sql is None


def test_case_insensitivity_and_quoting() -> None:
    """Validator should be case-insensitive for table names and forbidden functions."""
    sql1 = 'SELECT * FROM "Artist"'
    res1 = validate_and_transform_sql(sql1, valid_tables=VALID_TABLES)
    assert res1.is_valid is True
    assert res1.tables_referenced == ["artist"]

    sql2 = "SELECT PG_SLEEP(5)"
    res2 = validate_and_transform_sql(sql2, valid_tables=VALID_TABLES)
    assert res2.is_valid is False
