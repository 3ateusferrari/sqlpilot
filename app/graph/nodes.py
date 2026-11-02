"""Graph node implementations for the SQLPilot base linear flow."""

import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from psycopg.rows import dict_row

from app.db.schema_loader import load_schema
from app.db.session import get_readonly_connection
from app.graph.llm import get_llm
from app.graph.prompts import SYSTEM_PROMPT_NL_RESPONSE, SYSTEM_PROMPT_SQL_GEN
from app.graph.state import AgentState, GeneratedSQL
from app.logging import get_logger

logger = get_logger(__name__)


def _serialize_value(val: Any) -> Any:
    """Serialize non-JSON types (Decimal, datetime, date, UUID, bytes) to JSON-safe primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date, time)):
        return val.isoformat()
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, list):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val


async def carregar_schema_node(state: AgentState) -> dict[str, Any]:
    """Load database schema DDL and valid tables list into the graph state."""
    logger.info("carregar_schema_node_executing")
    tables, schema_str = await load_schema()
    return {
        "schema_context": schema_str,
        "valid_tables": tables,
    }


async def gerar_sql_node(state: AgentState) -> dict[str, Any]:
    """Generate SQL query and analytical reasoning from natural language question."""
    logger.info("gerar_sql_node_executing", pergunta=state.get("pergunta"))

    schema_context = state.get("schema_context", "")
    pergunta = state.get("pergunta", "")

    system_message = SYSTEM_PROMPT_SQL_GEN.format(schema_context=schema_context)
    human_content = f"Pergunta do usuário: {pergunta}"

    messages = [
        SystemMessage(content=system_message),
        HumanMessage(content=human_content),
    ]

    llm = get_llm()
    structured_llm = llm.with_structured_output(GeneratedSQL)
    res = await structured_llm.ainvoke(messages)

    if isinstance(res, GeneratedSQL):
        sql = res.sql
        reasoning = res.reasoning
    elif isinstance(res, dict):
        sql = str(res.get("sql", ""))
        reasoning = str(res.get("reasoning", ""))
    else:
        sql = getattr(res, "sql", str(res))
        reasoning = getattr(res, "reasoning", "")

    logger.info("gerar_sql_node_completed", sql=sql)
    return {
        "sql_gerado": sql,
        "raciocinio_sql": reasoning,
        "sql_final": sql,
    }


async def executar_sql_node(state: AgentState) -> dict[str, Any]:
    """Execute SQL query against PostgreSQL readonly connection and capture results."""
    sql_to_run = state.get("sql_final") or state.get("sql_gerado")
    if not sql_to_run:
        logger.warning("executar_sql_node_empty_sql")
        return {
            "resultado": [],
            "erro_execucao": "Nenhuma query SQL fornecida para execução.",
        }

    logger.info("executar_sql_node_executing", sql=sql_to_run)

    try:
        async with get_readonly_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql_to_run)
                raw_rows = await cur.fetchall()

        serialized_rows = [{k: _serialize_value(v) for k, v in row.items()} for row in raw_rows]
        logger.info("executar_sql_node_success", row_count=len(serialized_rows))
        return {
            "resultado": serialized_rows,
            "erro_execucao": None,
        }
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("executar_sql_node_failed", error=error_msg, sql=sql_to_run)
        return {
            "resultado": [],
            "erro_execucao": error_msg,
        }


async def responder_em_linguagem_natural_node(state: AgentState) -> dict[str, Any]:
    """Synthesize query results into a natural language response in Portuguese."""
    erro = state.get("erro_execucao")
    if erro:
        logger.info("responder_em_linguagem_natural_reporting_error", erro=erro)
        return {
            "resposta": (
                "Não foi possível obter os dados devido a um erro na execução "
                f"da consulta SQL: {erro}"
            )
        }

    pergunta = state.get("pergunta", "")
    resultado = state.get("resultado", [])

    logger.info("responder_em_linguagem_natural_synthesizing", result_count=len(resultado))

    prompt_user = (
        f"Pergunta original do usuário:\n{pergunta}\n\n"
        f"Dados retornados da consulta SQL:\n{json.dumps(resultado, ensure_ascii=False, indent=2)}"
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT_NL_RESPONSE),
        HumanMessage(content=prompt_user),
    ]

    llm = get_llm()
    ai_msg = await llm.ainvoke(messages)
    resposta = ai_msg.content if isinstance(ai_msg.content, str) else str(ai_msg.content)

    return {"resposta": resposta}
