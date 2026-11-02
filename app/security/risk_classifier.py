"""Deterministic AST-based SQL risk classifier."""

from __future__ import annotations

from typing import Self

import sqlglot
from pydantic import BaseModel, Field, model_validator
from sqlglot import exp

from app.graph.state import RiskLevel
from app.security.validator import _is_pure_scalar_aggregation, _resolve_physical_tables

SENSITIVE_TABLES: frozenset[str] = frozenset({"employee", "customer", "invoice"})
PII_COLUMNS: frozenset[str] = frozenset({"email", "phone", "address", "birth_date", "postal_code"})
FACT_TABLES: frozenset[str] = frozenset({"track", "invoice_line", "playlist_track"})


class DeterministicRiskResult(BaseModel):
    """Deterministic risk evaluation result from AST analysis."""

    level: RiskLevel = "low"
    reasons: list[str] = Field(default_factory=list)
    sensitive_tables_accessed: list[str] = Field(default_factory=list)
    pii_columns_accessed: list[str] = Field(default_factory=list)
    join_count: int = 0
    has_cross_join: bool = False
    missing_where_on_fact_tables: bool = False
    nivel_risco: RiskLevel = "low"
    motivos_risco: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_portuguese_fields(self) -> Self:
        """Synchronize English and Portuguese state field names."""
        if self.level and self.nivel_risco == "low" and self.level != "low":
            self.nivel_risco = self.level
        elif self.nivel_risco and self.level == "low" and self.nivel_risco != "low":
            self.level = self.nivel_risco

        if self.reasons and not self.motivos_risco:
            self.motivos_risco = list(self.reasons)
        elif self.motivos_risco and not self.reasons:
            self.reasons = list(self.motivos_risco)
        return self


# Alias for compatibility
RiskAssessment = DeterministicRiskResult


def _extract_direct_tables(sel: exp.Select) -> set[str]:
    """Extract physical or aliased table names directly referenced in a Select node's FROM and JOINs."""
    direct_tables: set[str] = set()
    from_clause = sel.args.get("from_")
    if from_clause:
        for t in from_clause.find_all(exp.Table):
            if t.find_ancestor(exp.Select) is sel:
                t_name = t.name.strip('"').lower() if t.name else ""
                if t_name:
                    direct_tables.add(t_name)

    for j in sel.args.get("joins") or []:
        for t in j.find_all(exp.Table):
            if t.find_ancestor(exp.Select) is sel:
                t_name = t.name.strip('"').lower() if t.name else ""
                if t_name:
                    direct_tables.add(t_name)

    return direct_tables


def _is_table_exposed_without_aggregation(ast: sqlglot.Expr, table_name: str) -> bool:
    """Check if table_name is exposed without aggregation (GROUP BY or scalar agg)."""
    normalized_target = table_name.strip('"').lower()

    for sel in ast.find_all(exp.Select):
        direct_tables = _extract_direct_tables(sel)
        if normalized_target in direct_tables:
            has_group = sel.args.get("group") is not None
            is_scalar = _is_pure_scalar_aggregation(sel)
            if not has_group and not is_scalar:
                return True

    return False


def _is_table_unfiltered_and_unaggregated(ast: sqlglot.Expr, table_name: str) -> bool:
    """Check if table_name is queried without scoped WHERE and without aggregation."""
    normalized_target = table_name.strip('"').lower()

    for sel in ast.find_all(exp.Select):
        direct_tables = _extract_direct_tables(sel)
        if normalized_target in direct_tables:
            has_where = sel.args.get("where") is not None
            has_group = sel.args.get("group") is not None
            is_scalar = _is_pure_scalar_aggregation(sel)
            if not has_where and not has_group and not is_scalar:
                return True

    return False


def _is_tautological_condition(node: sqlglot.Expr | None) -> bool:
    """Check if condition is a constant tautology like TRUE or 1=1."""
    if node is None:
        return False
    inner = node.unnest() if hasattr(node, "unnest") else node
    if isinstance(inner, exp.Boolean) and inner.this is True:
        return True
    if isinstance(inner, exp.EQ):
        left = inner.left.unnest() if hasattr(inner.left, "unnest") else inner.left
        right = inner.right.unnest() if hasattr(inner.right, "unnest") else inner.right
        if isinstance(left, exp.Literal) and isinstance(right, exp.Literal):
            if str(left.this) == str(right.this):
                return True
    return False


def analyze_ast_risk(sql: str) -> DeterministicRiskResult:
    """Analyze SQL query risk deterministically using AST inspection.

    Args:
        sql: SQL query string to inspect.

    Returns:
        DeterministicRiskResult with risk level, reasons, and structural metrics.
    """
    if not sql or not sql.strip():
        return DeterministicRiskResult(
            level="high",
            reasons=["Query SQL vazia ou inválida."],
            nivel_risco="high",
            motivos_risco=["Query SQL vazia ou inválida."],
        )

    try:
        parsed = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except Exception as exc:
        return DeterministicRiskResult(
            level="high",
            reasons=[f"Erro de parsing SQL: {exc}"],
            nivel_risco="high",
            motivos_risco=[f"Erro de parsing SQL: {exc}"],
        )

    if not parsed:
        return DeterministicRiskResult(
            level="high",
            reasons=["Query SQL vazia ou inválida."],
            nivel_risco="high",
            motivos_risco=["Query SQL vazia ou inválida."],
        )

    if len(parsed) > 1:
        return DeterministicRiskResult(
            level="high",
            reasons=["Múltiplos statements SQL não são permitidos por segurança."],
            nivel_risco="high",
            motivos_risco=["Múltiplos statements SQL não são permitidos por segurança."],
        )

    ast = parsed[0]
    reasons: list[str] = []

    # 1. Resolve referenced physical tables (excluding CTE aliases)
    physical_tables = _resolve_physical_tables(ast)
    physical_tables_set = {t.name.strip('"').lower() for t in physical_tables if t.name}

    # 2. Sensitive tables & PII column detection
    sensitive_tables_accessed = sorted(t for t in physical_tables_set if t in SENSITIVE_TABLES)
    pii_columns_accessed: list[str] = []

    if sensitive_tables_accessed:
        pii_found: set[str] = set()
        for col in ast.find_all(exp.Column):
            c_name = col.name.strip('"').lower() if col.name else ""
            if c_name in PII_COLUMNS:
                pii_found.add(c_name)

        if pii_found:
            pii_columns_accessed = sorted(pii_found)
            cols_str = ", ".join(pii_columns_accessed)
            reasons.append(f"Acesso a colunas com dados pessoais/PII: {cols_str}")

        for s_table in sensitive_tables_accessed:
            if _is_table_exposed_without_aggregation(ast, s_table):
                reasons.append(
                    f"Exposição de registros individuais da tabela sensível '{s_table}' sem agregação"
                )

    # 3. Missing WHERE on Fact tables (unaggregated and unfiltered queries)
    fact_tables_accessed = [t for t in sorted(physical_tables_set) if t in FACT_TABLES]
    missing_where_on_fact_tables = False
    if fact_tables_accessed:
        unfiltered_unaggregated = [
            ft for ft in fact_tables_accessed if _is_table_unfiltered_and_unaggregated(ast, ft)
        ]
        if unfiltered_unaggregated:
            missing_where_on_fact_tables = True
            for ft in unfiltered_unaggregated:
                reasons.append(
                    f"Consulta na tabela de fatos volumosa '{ft}' sem filtro WHERE e sem agregação"
                )

    # 4. Join complexity, cartesian joins, and tautological join conditions
    joins = list(ast.find_all(exp.Join))
    join_count = len(joins)
    if join_count >= 4:
        reasons.append(f"Consulta de alta complexidade contendo {join_count} JOINs")

    has_cross_join = False
    for j in joins:
        kind = (getattr(j, "kind", "") or "").upper()
        method = (getattr(j, "method", "") or "").upper()
        if not method and j.args.get("method"):
            method = str(j.args.get("method")).upper()
        is_natural = method == "NATURAL"
        on_clause = j.args.get("on")
        has_on = on_clause is not None
        has_using = j.args.get("using") is not None

        if kind == "CROSS":
            has_cross_join = True
            break
        if not has_on and not has_using and not is_natural:
            has_cross_join = True
            break
        if has_on and _is_tautological_condition(on_clause):
            has_cross_join = True
            break

    if has_cross_join:
        reasons.append("Presença de CROSS JOIN ou junção cartesiana sem condição ON")

    # 5. Level determination
    deduped_reasons = list(dict.fromkeys(reasons))
    level: RiskLevel = "high" if deduped_reasons else "low"

    return DeterministicRiskResult(
        level=level,
        reasons=deduped_reasons,
        sensitive_tables_accessed=sensitive_tables_accessed,
        pii_columns_accessed=pii_columns_accessed,
        join_count=join_count,
        has_cross_join=has_cross_join,
        missing_where_on_fact_tables=missing_where_on_fact_tables,
        nivel_risco=level,
        motivos_risco=deduped_reasons,
    )
