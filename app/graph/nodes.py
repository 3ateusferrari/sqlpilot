"""Graph node implementations for the SQLPilot base linear flow."""

import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from psycopg.rows import dict_row

from app.config import settings
from app.db.schema_loader import load_schema
from app.db.session import get_readonly_connection
from app.graph.llm import get_llm
from app.graph.prompts import SYSTEM_PROMPT_NL_RESPONSE, SYSTEM_PROMPT_SQL_GEN
from app.graph.state import AgentState, GeneratedSQL
from app.logging import get_logger
from app.security.validator import validate_and_transform_sql

logger = get_logger(__name__)


def _serialize_value(val: Any) -> Any:
    """Serialize non-JSON types (Decimal, datetime, date, UUID, bytes, set, tuple) to JSON-safe primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date, time)):
        return val.isoformat()
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, (list, tuple, set)):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val


def _clean_sql_markdown(sql: str) -> str:
    """Strip markdown code fence blocks (```sql ... ```) if present."""
    sql = sql.strip()
    if sql.startswith("```"):
        lines = sql.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            sql = "\n".join(lines[1:-1]).strip()
        else:
            sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return sql


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

    erros = state.get("erros_validacao")
    if erros:
        sql_gerado = state.get("sql_gerado", "")
        erros_str = "; ".join(erros) if isinstance(erros, list) else str(erros)
        retry_context = (
            f"\n\nTentativa anterior: {sql_gerado}\n"
            f"Erros encontrados na validação: {erros_str}\n"
            "Por favor, corrija o SQL evitando esses erros e mantendo o schema Chinook."
        )
        human_content += retry_context

    messages = [
        SystemMessage(content=system_message),
        HumanMessage(content=human_content),
    ]

    llm = get_llm()
    structured_llm = llm.with_structured_output(GeneratedSQL)
    res = await structured_llm.ainvoke(messages)

    if res is None:
        sql = ""
        reasoning = ""
    elif isinstance(res, GeneratedSQL):
        sql = res.sql
        reasoning = res.reasoning
    elif isinstance(res, dict):
        sql = str(res.get("sql", ""))
        reasoning = str(res.get("reasoning", ""))
    else:
        sql = getattr(res, "sql", str(res))
        reasoning = getattr(res, "reasoning", "")

    sql = _clean_sql_markdown(sql)

    logger.info("gerar_sql_node_completed", sql=sql)
    return {
        "sql_gerado": sql,
        "raciocinio_sql": reasoning,
    }


async def validar_sql_node(state: AgentState) -> dict[str, Any]:
    """Validate generated SQL query against AST security rules and Chinook schema.

    Enforces read-only SELECT instructions, valid tables whitelist, and automatic
    LIMIT clamping/injection.
    """
    sql = state.get("sql_gerado") or ""
    valid_tables = state.get("valid_tables") or []
    logger.info("validar_sql_node_executing", sql=sql)

    res = validate_and_transform_sql(
        sql=sql,
        valid_tables=valid_tables,
        default_limit=settings.default_row_limit,
        max_limit=1000,
    )

    if res.is_valid:
        logger.info("validar_sql_node_valid", transformed_sql=res.transformed_sql)
        return {
            "sql_final": res.transformed_sql,
            "erros_validacao": [],
        }

    tentativas = state.get("tentativas", 0) + 1
    logger.warning("validar_sql_node_invalid", errors=res.errors, tentativas=tentativas)
    return {
        "tentativas": tentativas,
        "erros_validacao": res.errors,
        "sql_final": "",
    }


async def executar_sql_node(state: AgentState) -> dict[str, Any]:
    """Execute SQL query against PostgreSQL readonly connection and capture results."""
    sql_to_run = state.get("sql_final")
    if not sql_to_run:
        logger.warning("executar_sql_node_missing_validated_sql")
        return {
            "resultado": [],
            "erro_execucao": "Nenhuma query SQL validada disponível para execução.",
        }

    logger.info("executar_sql_node_executing", sql=sql_to_run)

    try:
        async with get_readonly_connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(sql_to_run)
                if cur.description:
                    raw_rows = await cur.fetchall()
                else:
                    raw_rows = []

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
    erros_validacao = state.get("erros_validacao")
    if erros_validacao:
        logger.info(
            "responder_em_linguagem_natural_reporting_validation_errors", erros=erros_validacao
        )
        erros_str = (
            "; ".join(erros_validacao)
            if isinstance(erros_validacao, list)
            else str(erros_validacao)
        )
        return {
            "resposta": (
                f"Não foi possível processar a consulta devido a erros de validação: {erros_str}"
            )
        }

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

    limit = settings.default_row_limit
    if len(resultado) > limit:
        resultado_to_send = resultado[:limit]
        truncation_notice = f"\n(Nota: Exibindo apenas os primeiros {limit} de {len(resultado)} registros retornados.)"
    else:
        resultado_to_send = resultado
        truncation_notice = ""

    prompt_user = (
        f"Pergunta original do usuário:\n{pergunta}\n\n"
        f"Dados retornados da consulta SQL:\n"
        f"{json.dumps(resultado_to_send, ensure_ascii=False, indent=2)}"
        f"{truncation_notice}"
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT_NL_RESPONSE),
        HumanMessage(content=prompt_user),
    ]

    llm = get_llm()
    ai_msg = await llm.ainvoke(messages)

    if isinstance(ai_msg.content, str):
        resposta = ai_msg.content
    elif isinstance(ai_msg.content, list):
        text_parts = [
            block["text"]
            if isinstance(block, dict) and "text" in block
            else getattr(block, "text", str(block))
            for block in ai_msg.content
        ]
        resposta = "".join(text_parts) if text_parts else str(ai_msg.content)
    else:
        resposta = str(ai_msg.content)

    return {"resposta": resposta}
