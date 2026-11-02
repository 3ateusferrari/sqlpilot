"""Conditional edge routing functions for SQLPilot execution graph."""

from app.config import settings
from app.graph.state import AgentState
from app.logging import get_logger

logger = get_logger(__name__)


def route_after_validation(state: AgentState) -> str:
    """Route after SQL validation based on errors and retry count.

    If validation errors exist:
        - If tentativas < settings.max_validation_retries (default 3):
            return "gerar_sql" (self-correction retry)
        - Else:
            return "responder_em_linguagem_natural" (exhausted retries, report errors)
    If validation passed (no errors):
        - Return "executar_sql"

    Args:
        state: Current AgentState.

    Returns:
        Name of the next node to execute.
    """
    erros = state.get("erros_validacao")
    if erros:
        tentativas = state.get("tentativas", 0)
        if tentativas < settings.max_validation_retries:
            logger.info(
                "route_after_validation_retry",
                tentativas=tentativas,
                max_retries=settings.max_validation_retries,
            )
            return "gerar_sql"

        logger.warning(
            "route_after_validation_exhausted",
            tentativas=tentativas,
            max_retries=settings.max_validation_retries,
        )
        return "responder_em_linguagem_natural"

    logger.info("route_after_validation_success")
    return "executar_sql"
