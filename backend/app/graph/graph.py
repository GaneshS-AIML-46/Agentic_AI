from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.graph.nodes import (
    explain_node,
    parse_node,
    rag_node,
    replan_node,
    should_replan,
    solve_node,
    specialists_node,
    supervisor_node,
    validate_node,
)
from app.graph.state import GraphState


def build_graph(db: Session):
    graph = StateGraph(GraphState)
    graph.add_node("parse", parse_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("rag", partial(rag_node, db))
    graph.add_node("specialists", partial(specialists_node, db))
    graph.add_node("solve", solve_node)
    graph.add_node("validate", validate_node)
    graph.add_node("replan", replan_node)
    graph.add_node("explain", explain_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "supervisor")
    graph.add_edge("supervisor", "rag")
    graph.add_edge("rag", "specialists")
    graph.add_edge("specialists", "solve")
    graph.add_edge("solve", "validate")
    graph.add_conditional_edges(
        "validate",
        should_replan,
        {"replan": "replan", "explain": "explain"},
    )
    graph.add_edge("replan", "specialists")
    graph.add_edge("explain", END)
    return graph.compile()


def run_pipeline(db: Session, query: str, patch: dict | None = None) -> GraphState:
    app = build_graph(db)
    initial: GraphState = {"query": query, "replan_count": 0, "trace": []}
    if patch:
        initial["patch"] = patch
    return app.invoke(initial)
