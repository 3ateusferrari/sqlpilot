"""Unit tests for graph state, LLM factory, prompts, and node helpers."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any, get_type_hints
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

from app.config import settings
from app.graph.llm import get_llm
from app.graph.nodes import (
    _clean_sql_markdown,
    _serialize_value,
    executar_sql_node,
    gerar_sql_node,
    responder_em_linguagem_natural_node,
)
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
        "explain_metrics": dict[str, object],
        "decisao_humana": dict[str, object] | None,
        "human_verified": bool,
        "sql_final": str,
        "resultado": list[dict[str, object]],
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


def test_get_llm_respects_settings_temperature(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_llm defaults to settings.llm_temperature when not explicitly specified."""
    monkeypatch.setattr(settings, "llm_temperature", 0.7)
    llm = get_llm()
    assert llm.temperature == 0.7


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


def test_serialize_value_types() -> None:
    """Verify _serialize_value serializes Decimal, datetime, UUID, set, tuple, bytes."""
    # Decimal
    assert _serialize_value(Decimal("42.50")) == 42.5
    # Datetime / Date / Time
    dt = datetime(2026, 11, 2, 12, 30, tzinfo=UTC)
    assert _serialize_value(dt) == dt.isoformat()
    d = date(2026, 11, 2)
    assert _serialize_value(d) == d.isoformat()
    t = time(12, 30)
    assert _serialize_value(t) == t.isoformat()
    # UUID
    u = UUID("12345678-1234-5678-1234-567812345678")
    assert _serialize_value(u) == "12345678-1234-5678-1234-567812345678"
    # Bytes
    assert _serialize_value(b"test-bytes") == "test-bytes"
    # Tuple and Set
    tup_res = _serialize_value((Decimal("1.5"), "abc"))
    assert tup_res == [1.5, "abc"]
    set_res = _serialize_value({10, 20})
    assert isinstance(set_res, list)
    assert set(set_res) == {10, 20}
    # Nested dict
    nested = {"key": Decimal("9.99"), "items": [date(2026, 1, 1)]}
    assert _serialize_value(nested) == {"key": 9.99, "items": ["2026-01-01"]}


def test_clean_sql_markdown() -> None:
    """Verify _clean_sql_markdown strips code blocks with or without language tags."""
    assert _clean_sql_markdown("```sql\nSELECT * FROM artist;\n```") == "SELECT * FROM artist;"
    assert _clean_sql_markdown("```\nSELECT 1;\n```") == "SELECT 1;"
    assert _clean_sql_markdown("SELECT 1;") == "SELECT 1;"


@pytest.mark.asyncio
async def test_gerar_sql_node_cleans_markdown_and_handles_none() -> None:
    """Verify gerar_sql_node strips backticks and handles None responses gracefully."""
    mock_llm = MagicMock()
    mock_runnable = MagicMock()
    # Return markdown wrapped SQL
    mock_runnable.ainvoke = AsyncMock(
        return_value=GeneratedSQL(
            sql="```sql\nSELECT * FROM artist LIMIT 5;\n```",
            reasoning="Busca 5 artistas com bloco markdown.",
        )
    )
    mock_llm.with_structured_output.return_value = mock_runnable

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        state: AgentState = {"pergunta": "5 artistas", "schema_context": "..."}
        update = await gerar_sql_node(state)

    assert update["sql_gerado"] == "SELECT * FROM artist LIMIT 5;"
    assert update["sql_final"] == "SELECT * FROM artist LIMIT 5;"

    # Test None response from LLM
    mock_runnable.ainvoke = AsyncMock(return_value=None)
    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        update_none = await gerar_sql_node(state)

    assert update_none["sql_gerado"] == ""
    assert update_none["raciocinio_sql"] == ""


@pytest.mark.asyncio
async def test_responder_em_linguagem_natural_content_blocks() -> None:
    """Verify responder_em_linguagem_natural_node handles list content blocks from Claude."""
    mock_llm = MagicMock()
    content_blocks = [
        {"type": "text", "text": "Os principais artistas "},
        {"type": "text", "text": "são Iron Maiden e AC/DC."},
    ]
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=content_blocks))  # type: ignore[arg-type]

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        state: AgentState = {
            "pergunta": "Artistas",
            "resultado": [{"name": "Iron Maiden"}],
            "erro_execucao": None,
        }
        update = await responder_em_linguagem_natural_node(state)

    assert update["resposta"] == "Os principais artistas são Iron Maiden e AC/DC."


@pytest.mark.asyncio
async def test_responder_em_linguagem_natural_truncation_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that responder_em_linguagem_natural_node truncates large result sets in prompt."""
    monkeypatch.setattr(settings, "default_row_limit", 2)
    mock_llm = MagicMock()
    captured_messages: list[Any] = []

    async def fake_ainvoke(messages: list[Any]) -> AIMessage:
        captured_messages.extend(messages)
        return AIMessage(content="Resposta sintetizada.")

    mock_llm.ainvoke = fake_ainvoke

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        state: AgentState = {
            "pergunta": "Muitos dados",
            "resultado": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
            "erro_execucao": None,
        }
        await responder_em_linguagem_natural_node(state)

    prompt_content = captured_messages[1].content
    assert "Exibindo apenas os primeiros 2 de 4 registros retornados." in prompt_content


@pytest.mark.asyncio
async def test_executar_sql_node_no_description_query() -> None:
    """Verify executar_sql_node handles statements with cur.description=None cleanly."""
    from contextlib import asynccontextmanager

    mock_cur = AsyncMock()
    mock_cur.description = None
    mock_cur.fetchall = AsyncMock()

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__aexit__ = AsyncMock(return_value=None)

    @asynccontextmanager
    async def fake_connection() -> Any:
        yield mock_conn

    with patch("app.graph.nodes.get_readonly_connection", side_effect=fake_connection):
        state: AgentState = {"sql_final": "SET statement_timeout = 5000;"}
        update = await executar_sql_node(state)

    assert update["resultado"] == []
    assert update["erro_execucao"] is None
    # fetchall should NOT have been called since cur.description was None
    mock_cur.fetchall.assert_not_called()
