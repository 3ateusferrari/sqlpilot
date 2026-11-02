"""Graph state models and typing definitions for SQLPilot."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "high"]
HumanAction = Literal["approve", "edit", "reject"]


class GeneratedSQL(BaseModel):
    """Structured output representation for generated SQL queries."""

    sql: str = Field(
        description="Query SQL PostgreSQL válida, contendo apenas uma instrução SELECT."
    )
    reasoning: str = Field(description="Breve explicação das tabelas e joins escolhidos.")


class HumanDecision(BaseModel):
    """Payload representing a human review decision in HITL flow."""

    action: HumanAction = Field(description="Ação tomada pelo revisor: approve, edit ou reject.")
    edited_sql: str | None = Field(
        default=None,
        description="Query SQL corrigida manualmente caso a ação seja edit.",
    )
    feedback: str | None = Field(
        default=None,
        description="Feedback textual com instruções para regeneração caso a ação seja reject.",
    )
    reviewer: str = Field(
        default="anonymous",
        description="Identificação do usuário ou analista que realizou a revisão.",
    )


class ExplainMetrics(BaseModel):
    """Metrics extracted from PostgreSQL EXPLAIN (FORMAT JSON) plan."""

    estimated_rows: int = Field(
        default=0,
        description="Número total de linhas estimadas pelo planejador do PostgreSQL.",
    )
    total_cost: float = Field(
        default=0.0,
        description="Custo total estimado da query pelo planejador do PostgreSQL.",
    )
    has_seq_scan: bool = Field(
        default=False,
        description="Indica se o plano de execução contém Seq Scan.",
    )
    raw_plan: dict[str, Any] = Field(
        default_factory=dict,
        description="Estrutura completa do plano retornado pelo PostgreSQL.",
    )


class AgentState(TypedDict, total=False):
    """Global state of the SQLPilot execution graph."""

    pergunta: str
    schema_context: str
    valid_tables: list[str]
    sql_gerado: str
    raciocinio_sql: str
    erros_validacao: list[str]
    tentativas: int
    nivel_risco: RiskLevel
    motivos_risco: list[str]
    explain_metrics: dict[str, Any]
    decisao_humana: dict[str, Any] | None
    human_verified: bool
    sql_final: str
    resultado: list[dict[str, Any]]
    erro_execucao: str | None
    resposta: str
