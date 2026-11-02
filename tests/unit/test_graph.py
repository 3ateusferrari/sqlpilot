"""Unit tests for graph state, LLM factory, and prompts."""

from typing import get_type_hints

import pytest
from langchain_anthropic import ChatAnthropic

from app.config import settings
from app.graph.llm import get_llm
from app.graph.prompts import SYSTEM_PROMPT_NL_RESPONSE, SYSTEM_PROMPT_SQL_GEN
from app.graph.state import (
    AgentState,
    ExplainMetrics,
    GeneratedSQL,
    HumanAction,
    HumanDecision,
    RiskLevel,
)


def test_state_models_definition() -> None:
    """Verify that all state models have expected fields and types."""
    # GeneratedSQL
    sql_model = GeneratedSQL(
        sql="SELECT * FROM artist LIMIT 5;",
        reasoning="Consulta os 5 primeiros artistas.",
    )
    assert sql_model.sql == "SELECT * FROM artist LIMIT 5;"
    assert sql_model.reasoning == "Consulta os 5 primeiros artistas."

    # HumanDecision
    action: HumanAction = "approve"
    decision = HumanDecision(
        action=action,
        edited_sql=None,
        feedback=None,
        reviewer="admin",
    )
    assert decision.action == "approve"
    assert decision.reviewer == "admin"

    # HumanDecision with edit
    decision_edit = HumanDecision(
        action="edit",
        edited_sql="SELECT name FROM artist LIMIT 3;",
        feedback="Apenas nome e limite 3",
    )
    assert decision_edit.action == "edit"
    assert decision_edit.edited_sql == "SELECT name FROM artist LIMIT 3;"

    # ExplainMetrics
    metrics = ExplainMetrics(
        estimated_rows=150,
        total_cost=24.5,
        has_seq_scan=True,
        raw_plan={"Plan": {"Total Cost": 24.5}},
    )
    assert metrics.estimated_rows == 150
    assert metrics.total_cost == 24.5
    assert metrics.has_seq_scan is True
    assert metrics.raw_plan["Plan"]["Total Cost"] == 24.5

    # ExplainMetrics defaults
    default_metrics = ExplainMetrics()
    assert default_metrics.estimated_rows == 0
    assert default_metrics.total_cost == 0.0
    assert default_metrics.has_seq_scan is False
    assert default_metrics.raw_plan == {}


def test_agent_state_annotations() -> None:
    """Verify that AgentState includes all required fields from the specification."""
    hints = get_type_hints(AgentState)
    expected_fields = {
        "pergunta": str,
        "schema_context": str,
        "valid_tables": list[str],
        "sql_gerado": str,
        "raciocinio_sql": str,
        "erros_validacao": list[str],
        "tentativas": int,
        "nivel_risco": RiskLevel,
        "motivos_risco": list[str],
        "explain_metrics": dict[str, object],  # dict[str, Any]
        "decisao_humana": dict[str, object] | None,  # dict[str, Any] | None
        "human_verified": bool,
        "sql_final": str,
        "resultado": list[dict[str, object]],  # list[dict[str, Any]]
        "erro_execucao": str | None,
        "resposta": str,
    }

    for field_name in expected_fields:
        assert field_name in hints, f"Missing field in AgentState: {field_name}"


def test_get_llm_defaults(clean_env: pytest.MonkeyPatch) -> None:
    """Verify get_llm instantiates ChatAnthropic with default settings."""
    llm = get_llm()
    assert isinstance(llm, ChatAnthropic)
    assert llm.model == "claude-haiku-4-5"
    assert llm.temperature == 0.0
    # Empty anthropic_api_key in settings should fallback to mock-key
    assert llm.anthropic_api_key.get_secret_value() == "mock-key"


def test_get_llm_custom_parameters() -> None:
    """Verify get_llm supports custom model and temperature overrides."""
    llm = get_llm(model="claude-3-opus-20240229", temperature=0.5)
    assert llm.model == "claude-3-opus-20240229"
    assert llm.temperature == 0.5


def test_get_llm_with_configured_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_llm uses the configured API key if present in settings."""
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-key-12345")
    llm = get_llm()
    assert llm.anthropic_api_key.get_secret_value() == "sk-ant-test-key-12345"


def test_system_prompts_content() -> None:
    """Verify system prompts contain mandatory instructions in Portuguese."""
    assert "PostgreSQL" in SYSTEM_PROMPT_SQL_GEN
    assert "Chinook" in SYSTEM_PROMPT_SQL_GEN
    assert "SELECT" in SYSTEM_PROMPT_SQL_GEN
    assert "português" in SYSTEM_PROMPT_NL_RESPONSE.lower()
