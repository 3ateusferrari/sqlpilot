"""Integration tests for the base linear graph execution."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.db.session import close_pools
from app.graph.builder import build_linear_graph
from app.graph.nodes import (
    carregar_schema_node,
    executar_sql_node,
    gerar_sql_node,
    responder_em_linguagem_natural_node,
)
from app.graph.state import AgentState, GeneratedSQL


@pytest.fixture(autouse=True)
async def cleanup_db_pools() -> AsyncIterator[None]:
    """Ensure pools are cleanly closed after each test."""
    yield
    await close_pools()


@pytest.mark.asyncio
async def test_carregar_schema_node_populates_state() -> None:
    """Validate that carregar_schema_node fetches valid tables and Chinook schema."""
    state: AgentState = {"pergunta": "Quais são os 5 artistas com mais álbuns?"}
    update = await carregar_schema_node(state)

    assert "schema_context" in update
    assert "valid_tables" in update
    assert len(update["valid_tables"]) == 11
    assert "CREATE TABLE artist" in update["schema_context"]
    assert "CREATE TABLE album" in update["schema_context"]


@pytest.mark.asyncio
async def test_gerar_sql_node_invokes_structured_output() -> None:
    """Validate that gerar_sql_node calls the LLM with structured output."""
    mock_llm = MagicMock()
    mock_runnable = MagicMock()
    mock_output = GeneratedSQL(
        sql="SELECT ar.name, count(al.album_id) as total_albuns FROM artist ar JOIN album al ON ar.artist_id = al.artist_id GROUP BY ar.name ORDER BY total_albuns DESC LIMIT 5;",
        reasoning="Agrupamento de álbuns por artista com ordenação decrescente e limite de 5.",
    )
    mock_runnable.ainvoke = AsyncMock(return_value=mock_output)
    mock_llm.with_structured_output.return_value = mock_runnable

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        state: AgentState = {
            "pergunta": "Quais são os 5 artistas com mais álbuns?",
            "schema_context": "CREATE TABLE artist (artist_id integer, name text);",
        }
        update = await gerar_sql_node(state)

    assert update["sql_gerado"] == mock_output.sql
    assert update["raciocinio_sql"] == mock_output.reasoning
    assert "sql_final" not in update


@pytest.mark.asyncio
async def test_executar_sql_node_success() -> None:
    """Validate that executar_sql_node executes SQL query against real Chinook database."""
    query = (
        "SELECT ar.name, count(al.album_id) as total_albuns "
        "FROM artist ar JOIN album al ON ar.artist_id = al.artist_id "
        "GROUP BY ar.name ORDER BY total_albuns DESC LIMIT 5;"
    )
    state: AgentState = {"sql_final": query}
    update = await executar_sql_node(state)

    assert update["erro_execucao"] is None
    rows = update["resultado"]
    assert len(rows) == 5
    # The sample database contains AC/DC, Accept and Metallica with 2 albums each
    artist_names = [r["name"] for r in rows]
    assert "AC/DC" in artist_names
    assert "Accept" in artist_names
    assert "Metallica" in artist_names
    assert rows[0]["total_albuns"] == 2


@pytest.mark.asyncio
async def test_executar_sql_node_error_handling() -> None:
    """Validate that executar_sql_node catches exceptions and sets erro_execucao without crashing."""
    bad_query = "SELECT * FROM non_existent_table_xyz LIMIT 5;"
    state: AgentState = {"sql_final": bad_query}
    update = await executar_sql_node(state)

    assert update["resultado"] == []
    assert update["erro_execucao"] is not None
    assert "non_existent_table_xyz" in update["erro_execucao"]


@pytest.mark.asyncio
async def test_responder_em_linguagem_natural_node_success() -> None:
    """Validate that responder_em_linguagem_natural_node invokes LLM to synthesize data."""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content="Os 5 artistas com mais álbuns são: Iron Maiden (21 álbuns) e Led Zeppelin (14 álbuns)."
        )
    )

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        state: AgentState = {
            "pergunta": "Quais são os 5 artistas com mais álbuns?",
            "resultado": [
                {"name": "Iron Maiden", "total_albuns": 21},
                {"name": "Led Zeppelin", "total_albuns": 14},
            ],
            "erro_execucao": None,
        }
        update = await responder_em_linguagem_natural_node(state)

    assert "Iron Maiden" in update["resposta"]
    assert "Led Zeppelin" in update["resposta"]


@pytest.mark.asyncio
async def test_responder_em_linguagem_natural_node_with_error() -> None:
    """Validate that responder_em_linguagem_natural_node formats error explanation when erro_execucao is present."""
    state: AgentState = {
        "pergunta": "Consulta inválida",
        "resultado": [],
        "erro_execucao": 'relation "non_existent_table_xyz" does not exist',
    }
    update = await responder_em_linguagem_natural_node(state)

    assert "não foi possível" in update["resposta"].lower()
    assert "non_existent_table_xyz" in update["resposta"]


@pytest.mark.asyncio
async def test_full_linear_graph_end_to_end() -> None:
    """End-to-end integration test of the linear graph using real Chinook DB and mocked LLM."""
    expected_sql = (
        "SELECT ar.name, count(al.album_id) as total_albuns "
        "FROM artist ar JOIN album al ON ar.artist_id = al.artist_id "
        "GROUP BY ar.name ORDER BY total_albuns DESC LIMIT 5;"
    )
    expected_response = (
        "Os 5 artistas com mais álbuns no banco Chinook são: "
        "Iron Maiden (21 álbuns), Led Zeppelin (14 álbuns), Deep Purple (11 álbuns), "
        "Metallica (10 álbuns) e U2 (10 álbuns)."
    )

    mock_llm = MagicMock()

    # Mock structured output for gerar_sql
    mock_runnable = MagicMock()
    mock_runnable.ainvoke = AsyncMock(
        return_value=GeneratedSQL(
            sql=expected_sql,
            reasoning="Realiza inner join entre artist e album, agrupando por nome e ordenando decrescente.",
        )
    )
    mock_llm.with_structured_output.return_value = mock_runnable

    # Mock ainvoke for responder_em_linguagem_natural
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=expected_response))

    app = build_linear_graph()

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        final_state: dict[str, Any] = await app.ainvoke(
            {"pergunta": "Quais são os 5 artistas com mais álbuns?"}
        )

    # 1. Schema check
    assert "valid_tables" in final_state
    assert len(final_state["valid_tables"]) == 11
    assert "CREATE TABLE artist" in final_state["schema_context"]

    # 2. Generated SQL check
    assert final_state["sql_gerado"] == expected_sql
    assert "LIMIT 5" in final_state["sql_final"]
    assert "artist" in final_state["sql_final"].lower()
    assert "inner join" in final_state["raciocinio_sql"].lower()

    # 3. Execution check against Chinook
    assert final_state["erro_execucao"] is None
    results = final_state["resultado"]
    assert len(results) == 5
    artist_names = [r["name"] for r in results]
    assert "AC/DC" in artist_names
    assert "Accept" in artist_names
    assert "Metallica" in artist_names
    assert results[0]["total_albuns"] == 2

    # 4. Final NL response check
    assert final_state["resposta"] == expected_response


@pytest.mark.asyncio
async def test_full_linear_graph_sql_error_flow() -> None:
    """Test full linear graph graceful failure when LLM produces invalid SQL."""
    bad_sql = "SELECT nonexistent_col FROM artist;"
    mock_llm = MagicMock()

    mock_runnable = MagicMock()
    mock_runnable.ainvoke = AsyncMock(
        return_value=GeneratedSQL(
            sql=bad_sql,
            reasoning="Query com coluna inexistente para testar fluxo de erro.",
        )
    )
    mock_llm.with_structured_output.return_value = mock_runnable

    app = build_linear_graph()

    with patch("app.graph.nodes.get_llm", return_value=mock_llm):
        final_state: dict[str, Any] = await app.ainvoke({"pergunta": "Pergunta com erro"})

    assert final_state["sql_gerado"] == bad_sql
    assert final_state["resultado"] == []
    assert final_state["erro_execucao"] is not None
    assert "nonexistent_col" in final_state["erro_execucao"]
    assert "não foi possível" in final_state["resposta"].lower()
