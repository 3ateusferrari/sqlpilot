"""SQL AST validator using SQLGlot for security and schema conformance."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlglot
from pydantic import BaseModel, Field
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

if TYPE_CHECKING:
    from collections.abc import Iterable

FORBIDDEN_FUNCTIONS: frozenset[str] = frozenset(
    {
        "pg_sleep",
        "pg_sleep_for",
        "pg_sleep_until",
        "pg_terminate_backend",
        "pg_cancel_backend",
        "pg_read_file",
        "pg_write_file",
        "pg_read_binary_file",
        "pg_ls_dir",
        "pg_stat_file",
        "dblink",
        "dblink_exec",
        "lo_import",
        "lo_export",
        "lo_get",
        "lo_put",
        "lo_unlink",
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
    exp.Into,
)

ALLOWED_SCHEMAS: frozenset[str] = frozenset({"", "public"})

FORBIDDEN_SCHEMAS: frozenset[str] = frozenset(
    {
        "pg_catalog",
        "information_schema",
        "internal",
    }
)


class ValidationResult(BaseModel):
    """Validation result containing status, errors, transformed SQL, and limit metadata."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    transformed_sql: str | None = None
    tables_referenced: list[str] = Field(default_factory=list)
    limit_injected: bool = False
    original_limit: int | None = None


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


def _is_aggregate_expression(expr: sqlglot.Expr) -> bool:
    """Check if an expression is an aggregate function or wrapped aggregate."""
    unaliased = expr.unalias()
    if unaliased.find(exp.Window) is not None:
        return False
    if isinstance(unaliased, exp.AggFunc):
        return True
    agg_funcs = list(unaliased.find_all(exp.AggFunc))
    if not agg_funcs:
        return False
    # If it contains an aggregate function, ensure all column references are within an aggregate
    for col in unaliased.find_all(exp.Column):
        if col.find_ancestor(exp.AggFunc) is None:
            return False
    return True


def _is_pure_scalar_aggregation(node: sqlglot.Expr) -> bool:
    """Check if node is a pure scalar aggregation without GROUP BY."""
    if not isinstance(node, exp.Select):
        return False
    if node.args.get("group") is not None:
        return False
    selects = node.selects
    if not selects:
        return False
    return all(_is_aggregate_expression(s) for s in selects)


def _extract_function_name(func_node: exp.Func | exp.Anonymous) -> str:
    """Extract lowercase function name from Func or Anonymous expression."""
    if isinstance(func_node, exp.Anonymous):
        return func_node.name.lower() if func_node.name else ""
    if hasattr(func_node, "sql_name"):
        sql_name = func_node.sql_name()
        if sql_name:
            return sql_name.lower()
    return type(func_node).__name__.lower()


def _resolve_physical_tables(ast: sqlglot.Expr) -> list[exp.Table]:
    """Extract physical table references, properly resolving CTE scopes.

    Uses `traverse_scope` to accurately identify whether a reference is a
    physical table (`exp.Table`) or resolves to a CTE scope (`Scope`).
    Falls back to AST inspection with schema qualification safeguards.
    """
    physical_tables: list[exp.Table] = []
    try:
        for scope in traverse_scope(ast):
            for source in scope.sources.values():
                if isinstance(source, exp.Table):
                    physical_tables.append(source)
    except Exception:
        # Fallback in case scope resolution encounters an unexpected structure
        cte_aliases = {cte.alias.strip('"').lower() for cte in ast.find_all(exp.CTE) if cte.alias}
        for table_node in ast.find_all(exp.Table):
            t_name = table_node.name.strip('"').lower() if table_node.name else ""
            if not t_name:
                continue
            # Tables with schema qualification (table.db) can never be CTEs
            if table_node.db or t_name not in cte_aliases:
                physical_tables.append(table_node)

    return physical_tables


def validate_and_transform_sql(
    sql: str,
    valid_tables: Iterable[str],
    default_limit: int = 100,
    max_limit: int = 1000,
) -> ValidationResult:
    """Validate SQL query via AST for read-only safety, table conformance, and limit enforcement.

    Args:
        sql: Raw SQL query string to validate.
        valid_tables: Whitelisted physical table names (case-insensitive).
        default_limit: Default LIMIT injected when query has no LIMIT clause.
        max_limit: Maximum allowed LIMIT value before clamping.

    Returns:
        ValidationResult indicating validity, errors, transformed SQL, referenced tables,
        and limit injection metadata.
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

    # 2. Mutating or dangerous expressions anywhere in AST (including exp.Into)
    for forbidden_node in ast.find_all(*FORBIDDEN_EXPRESSIONS):
        node_name = type(forbidden_node).__name__
        errors.append(f"Operação proibida detectada na AST: {node_name}.")

    # 3. Forbidden functions
    for func_node in ast.find_all(exp.Func, exp.Anonymous):
        fname = _extract_function_name(func_node)
        if fname in FORBIDDEN_FUNCTIONS:
            errors.append(f"Função proibida detectada: '{fname}'.")

    # 4. Strict Schema & Catalog Validation across all table nodes
    for table_node in ast.find_all(exp.Table):
        schema = table_node.db.strip('"').lower() if table_node.db else ""
        if schema and schema not in ALLOWED_SCHEMAS:
            errors.append(
                f"Acesso ao schema '{table_node.db}' não é permitido por segurança. "
                "Apenas o schema 'public' é autorizado."
            )

        catalog = table_node.catalog.strip('"').lower() if table_node.catalog else ""
        if catalog and catalog not in ALLOWED_SCHEMAS:
            errors.append(
                f"Acesso ao catálogo '{table_node.catalog}' não é permitido por segurança."
            )

    # 5. CTE and physical table resolution with traverse_scope
    normalized_valid_tables = {t.strip('"').lower() for t in valid_tables}
    available_tables_str = ", ".join(sorted(normalized_valid_tables))

    physical_tables = _resolve_physical_tables(ast)
    for table_node in physical_tables:
        t_name = table_node.name.strip('"').lower() if table_node.name else ""
        if not t_name:
            continue

        tables_referenced_set.add(t_name)

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

    # 6. Automatic LIMIT injection and clamping on root statement
    target = ast.unnest() if hasattr(ast, "unnest") else ast
    is_scalar_agg = _is_pure_scalar_aggregation(target)
    limit_injected = False
    original_limit: int | None = None

    if hasattr(target, "limit"):
        lim = target.args.get("limit")
        if lim is None:
            if not is_scalar_agg:
                target.limit(default_limit, copy=False)
                limit_injected = True
        else:
            expr = lim.expression
            numeric_limit: int | None = None
            if expr is not None:
                if isinstance(expr, exp.Var) and expr.name.upper() == "ALL":
                    target.limit(max_limit, copy=False)
                    limit_injected = True
                    original_limit = None
                else:
                    try:
                        numeric_limit = int(expr.this)
                    except (ValueError, TypeError, AttributeError):
                        numeric_limit = None

                    if numeric_limit is not None and numeric_limit > max_limit:
                        target.limit(max_limit, copy=False)
                        limit_injected = True
                        original_limit = numeric_limit

    transpiled_sql = ast.sql(dialect="postgres")
    return ValidationResult(
        is_valid=True,
        errors=[],
        transformed_sql=transpiled_sql,
        tables_referenced=sorted_tables,
        limit_injected=limit_injected,
        original_limit=original_limit,
    )
