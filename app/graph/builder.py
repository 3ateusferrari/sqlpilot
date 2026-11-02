"""Linear graph builder for SQLPilot."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    carregar_schema_node,
    executar_sql_node,
    gerar_sql_node,
    responder_em_linguagem_natural_node,
)
from app.graph.state import AgentState


def build_linear_graph() -> CompiledStateGraph:
    """Build and compile the base linear SQLPilot StateGraph.

    The execution flow is:
        START -> carregar_schema -> gerar_sql -> executar_sql -> responder_em_linguagem_natural -> END

    Returns:
        CompiledStateGraph ready for asynchronous invocation.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("carregar_schema", carregar_schema_node)
    workflow.add_node("gerar_sql", gerar_sql_node)
    workflow.add_node("executar_sql", executar_sql_node)
    workflow.add_node("responder_em_linguagem_natural", responder_em_linguagem_natural_node)

    workflow.add_edge(START, "carregar_schema")
    workflow.add_edge("carregar_schema", "gerar_sql")
    workflow.add_edge("gerar_sql", "executar_sql")
    workflow.add_edge("executar_sql", "responder_em_linguagem_natural")
    workflow.add_edge("responder_em_linguagem_natural", END)

    return workflow.compile()
