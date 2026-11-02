"""SQL AST validator using SQLGlot for security and schema conformance."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlglot
from pydantic import BaseModel, Field
from sqlglot import exp

if TYPE_CHECKING:
    from collections.abc import Iterable

FORBIDDEN_FUNCTIONS: frozenset[str] = frozenset(
    {
        "pg_sleep",
        "pg_read_file",
        "pg_write_file",
        "pg_read_binary_file",
        "dblink",
        "dblink_exec",
        "lo_import",
        "lo_export",
        "set_config",
        "current_setting",
        "query_to_xml",
    }
)

FORBIDDEN_EXPRESSIONS: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Grant,
    exp.Revoke,
    exp.Copy,
    exp.Create,
    exp.TruncateTable,
    exp.Merge,
    exp.Lock,
    exp.Set,
    exp.Pragma,
)

FORBIDDEN_SCHEMAS: frozenset[str] = frozenset(
    {
        "pg_catalog",
        "information_schema",
        "internal",
    }
)


class ValidationResult(BaseModel):
    """Validation result containing status, errors, and transformed SQL."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    transformed_sql: str | None = None
    tables_referenced: list[str] = Field(default_factory=list)


def _is_select_tree(node: sqlglot.Expr) -> bool:
    """Check if the expression tree is strictly SELECT or UNION of SELECTs."""
    inner = node.unnest() if hasattr(node, "unnest") else node
    if isinstance(inner, exp.Select):
        return True
    if isinstance(inner, exp.Union):
        left = inner.this
        right = inner.expression
        if isinstance(left, sqlglot.Expr) and isinstance(right, sqlglot.Expr):
            return _is_select_tree(left) and _is_select_tree(right)
        return False
    return False


def _extract_function_name(func_node: exp.Func | exp.Anonymous) -> str:
    """Extract lowercase function name from Func or Anonymous expression."""
    if isinstance(func_node, exp.Anonymous):
        return func_node.name.lower() if func_node.name else ""
    if hasattr(func_node, "sql_name"):
        sql_name = func_node.sql_name()
        if sql_name:
            return sql_name.lower()
    return type(func_node).__name__.lower()


def validate_and_transform_sql(
    sql: str,
    valid_tables: Iterable[str],
    default_limit: int = 100,
) -> ValidationResult:
    """Validate SQL query via AST for read-only safety, table conformance and single statement.

    Args:
        sql: Raw SQL query string to validate.
        valid_tables: Whitelisted physical table names (case-insensitive).
        default_limit: Default LIMIT for query transformation (reserved for ISSUE-06).

    Returns:
        ValidationResult indicating validity, errors, transformed SQL, and referenced tables.
    """
    if not sql or not sql.strip():
        return ValidationResult(
            is_valid=False,
            errors=["Query SQL vazia ou inválida."],
            transformed_sql=None,
            tables_referenced=[],
        )

    try:
        parsed = sqlglot.parse(sql, read="postgres")
    except Exception as exc:
        return ValidationResult(
            is_valid=False,
            errors=[f"Erro de sintaxe SQL: {exc}"],
            transformed_sql=None,
            tables_referenced=[],
        )

    statements = [stmt for stmt in parsed if stmt is not None]
    if not statements:
        return ValidationResult(
            is_valid=False,
            errors=["Query SQL vazia ou contém apenas delimitadores."],
            transformed_sql=None,
            tables_referenced=[],
        )

    if len(statements) > 1:
        return ValidationResult(
            is_valid=False,
            errors=["Múltiplos statements SQL não são permitidos por segurança."],
            transformed_sql=None,
            tables_referenced=[],
        )

    ast = statements[0]
    errors: list[str] = []
    tables_referenced_set: set[str] = set()

    # 1. Root verification: must be SELECT or UNION of SELECTs
    if not _is_select_tree(ast):
        errors.append("Apenas instruções SELECT (ou UNION de SELECTs) são permitidas.")

    # 2. Mutating or dangerous expressions anywhere in AST
    for forbidden_node in ast.find_all(*FORBIDDEN_EXPRESSIONS):
        node_name = type(forbidden_node).__name__
        errors.append(f"Operação proibida detectada na AST: {node_name}.")

    # 3. Forbidden functions
    for func_node in ast.find_all(exp.Func, exp.Anonymous):
        fname = _extract_function_name(func_node)
        if fname in FORBIDDEN_FUNCTIONS:
            errors.append(f"Função proibida detectada: '{fname}'.")

    # 4. CTE and physical table resolution
    cte_aliases = {cte.alias.strip('"').lower() for cte in ast.find_all(exp.CTE) if cte.alias}

    normalized_valid_tables = {t.strip('"').lower() for t in valid_tables}
    available_tables_str = ", ".join(sorted(normalized_valid_tables))

    for table_node in ast.find_all(exp.Table):
        t_name = table_node.name.strip('"').lower() if table_node.name else ""
        if not t_name:
            continue

        # Ignore if it's a CTE alias
        if t_name in cte_aliases:
            continue

        tables_referenced_set.add(t_name)

        # Check forbidden schema qualification
        schema = table_node.db.strip('"').lower() if table_node.db else ""
        if schema and schema in FORBIDDEN_SCHEMAS:
            errors.append(f"Acesso ao schema '{schema}' não é permitido por segurança.")

        catalog = table_node.catalog.strip('"').lower() if table_node.catalog else ""
        if catalog and catalog in FORBIDDEN_SCHEMAS:
            errors.append(f"Acesso ao catálogo '{catalog}' não é permitido por segurança.")

        # Whitelist validation
        if t_name not in normalized_valid_tables:
            errors.append(
                f"Tabela '{table_node.name}' não é permitida ou não existe. "
                f"Tabelas disponíveis: {available_tables_str}"
            )

    sorted_tables = sorted(tables_referenced_set)
    deduped_errors = list(dict.fromkeys(errors))

    if deduped_errors:
        return ValidationResult(
            is_valid=False,
            errors=deduped_errors,
            transformed_sql=None,
            tables_referenced=sorted_tables,
        )

    transpiled_sql = ast.sql(dialect="postgres")
    return ValidationResult(
        is_valid=True,
        errors=[],
        transformed_sql=transpiled_sql,
        tables_referenced=sorted_tables,
    )
