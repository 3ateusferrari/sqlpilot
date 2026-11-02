"""Integration tests for SQL validation and self-correction retry loop."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.db.session import close_pools, get_readonly_connection
from app.graph.builder import build_linear_graph
from app.graph.state import GeneratedSQL


@pytest.fixture(autouse=True)
async def cleanup_db_pools() -> AsyncIterator[None]:
    """Ensure pools are cleanly closed after each test."""
    yield
    await close_pools()


@pytest.mark.asyncio
async def test_validation_retry_self_correction_success() -> None:
    """Test 1: Self-correction on retry.

    LLM generates invalid table on 1st attempt ('SELECT * FROM artista_fantasma').
    validar_sql detects the error, increments tentativas to 1.
    Routes back to gerar_sql with error feedback in prompt, which then generates
    valid SQL ('SELECT * FROM artist').
    Validation succeeds (injects LIMIT 100), executes against Chinook and completes.
    """
    first_bad_sql = "SELECT * FROM artista_fantasma;"
    second_valid_sql = "SELECT * FROM artist;"
    final_nl_response = "Aqui estão os artistas cadastrados no banco Chinook."

    mock_llm = MagicMock()
    mock_runnable = MagicMock()

    captured_prompt_messages: list[list[Any]] = []

    async def fake_ainvoke(messages: list[Any]) -> GeneratedSQL:
        captured_prompt_messages.append(messages)
        if len(captured_prompt_messages) == 1:
            return GeneratedSQL(
                sql=first_bad_sql,
                reasoning="Tentativa com tabela em português.",
            )
        return GeneratedSQL(
            sql=second_valid_sql,
            reasoning="Correção para tabela artist existente no Chinook.",
        )

    mock_runnable.ainvoke = fake_ainvoke
    mock_llm.with_structured_output.return_value = mock_runnable
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=final_nl_response))

    app = build_linear_graph()

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        final_state: dict[str, Any] = await app.ainvoke({"pergunta": "Liste os artistas"})

    # 1. LLM was invoked twice for SQL generation (1 initial + 1 retry)
    assert len(captured_prompt_messages) == 2

    # 2. Check retry prompt injected error feedback on 2nd attempt
    second_call_human_msg = captured_prompt_messages[1][1].content
    assert "Tentativa anterior: SELECT * FROM artista_fantasma;" in second_call_human_msg
    assert "Erros encontrados na validação:" in second_call_human_msg
    assert "artista_fantasma" in second_call_human_msg
    assert (
        "Por favor, corrija o SQL evitando esses erros e mantendo o schema Chinook."
        in second_call_human_msg
    )

    # 3. Final state checks
    assert final_state["tentativas"] == 1
    assert final_state["erros_validacao"] == []
    assert final_state["sql_gerado"] == second_valid_sql
    assert "LIMIT 100" in final_state["sql_final"]
    assert final_state["erro_execucao"] is None
    assert len(final_state["resultado"]) > 0
    assert final_state["resposta"] == final_nl_response


@pytest.mark.asyncio
async def test_validation_retry_exhausted_retries() -> None:
    """Test 2: Persistent validation failure after 3 attempts.

    LLM persistently generates forbidden multi-statement / DROP TABLE SQL.
    The graph attempts 3 times (tentativas == 3), stops without executing SQL
    on the database, and reaches responder_em_linguagem_natural explaining validation errors.
    """
    dangerous_sql = "SELECT 1; DROP TABLE artist;"

    mock_llm = MagicMock()
    mock_runnable = MagicMock()

    call_count = 0

    async def fake_ainvoke(messages: list[Any]) -> GeneratedSQL:
        nonlocal call_count
        call_count += 1
        return GeneratedSQL(
            sql=dangerous_sql,
            reasoning="Query maliciosa ou com múltiplos comandos.",
        )

    mock_runnable.ainvoke = fake_ainvoke
    mock_llm.with_structured_output.return_value = mock_runnable

    app = build_linear_graph()

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        final_state: dict[str, Any] = await app.ainvoke(
            {"pergunta": "Tente apagar a tabela artist"}
        )

    # 1. Exactly 3 generation attempts
    assert call_count == 3
    assert final_state["tentativas"] == 3

    # 2. Validation errors captured
    assert len(final_state["erros_validacao"]) > 0
    assert any(
        "Múltiplos statements" in err or "Drop" in err for err in final_state["erros_validacao"]
    )

    # 3. Database execution never ran and sql_final was not validated
    assert final_state.get("resultado") is None or final_state.get("resultado") == []
    assert final_state.get("sql_final") in ("", None)

    # 4. Response explains the validation failure
    assert "validação" in final_state["resposta"].lower()

    # 5. Verify database integrity: artist table was NOT dropped
    async with get_readonly_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT count(*) FROM artist;")
            row = await cur.fetchone()
            assert row is not None and row[0] > 0


@pytest.mark.asyncio
async def test_validation_happy_path_first_attempt() -> None:
    """Test 3: Happy path (valid on 1st attempt).

    LLM generates valid SQL on the first try.
    validar_sql validates, automatically injects LIMIT 100, and executes on Chinook.
    """
    valid_sql = "SELECT name FROM artist ORDER BY artist_id;"
    mock_response = "Aqui está a lista ordenada de artistas."

    mock_llm = MagicMock()
    mock_runnable = MagicMock()
    mock_runnable.ainvoke = AsyncMock(
        return_value=GeneratedSQL(
            sql=valid_sql,
            reasoning="Ordena artistas por artist_id.",
        )
    )
    mock_llm.with_structured_output.return_value = mock_runnable
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=mock_response))

    app = build_linear_graph()

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        final_state: dict[str, Any] = await app.ainvoke({"pergunta": "Artistas ordenados"})

    # 1. Attempts count should be 0 (no failures)
    assert final_state.get("tentativas", 0) == 0
    assert final_state.get("erros_validacao") == []

    # 2. LIMIT 100 was injected into sql_final
    assert "LIMIT 100" in final_state["sql_final"]
    assert final_state["sql_gerado"] == valid_sql

    # 3. Execution succeeded against Chinook
    assert final_state["erro_execucao"] is None
    assert len(final_state["resultado"]) > 0
    assert final_state["resposta"] == mock_response
