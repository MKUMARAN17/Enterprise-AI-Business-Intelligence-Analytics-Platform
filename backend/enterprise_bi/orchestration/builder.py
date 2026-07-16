"""Assemble the multi-agent LangGraph.

The linear happy path is:

    guardrail → intent → schema → sql → validate → execute
              → analytics → viz → insight → END

with two conditional short-circuits (LangGraph conditional edges):
  * guardrail BLOCKED  → END (never call an LLM),
  * validate  BLOCKED  → END (never touch the DB),
  * execute   ERROR    → END (skip analytics/viz/insight, return the error).

``build_graph(deps)`` returns a compiled graph whose ``invoke(state)`` runs one
turn. Isolating construction here keeps ``OrchestrationService`` thin and lets
tests compile the real graph over fake deps.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from enterprise_bi.orchestration.agents import (
    make_analytics_node,
    make_execute_node,
    make_guardrail_node,
    make_insight_node,
    make_intent_node,
    make_schema_node,
    make_sql_node,
    make_validate_node,
    make_viz_node,
)
from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState


def _blocked(state: BIState) -> bool:
    return state.get("status") in {"BLOCKED", "ERROR"} or bool(state.get("error"))


# Node names are suffixed so they never collide with BIState keys (LangGraph
# forbids a node named the same as a state channel, e.g. `intent`/`sql`).
def _route_after_guardrail(state: BIState) -> str:
    return "END" if _blocked(state) else "intent_agent"


def _route_after_validate(state: BIState) -> str:
    return "END" if _blocked(state) else "execute_agent"


def _route_after_execute(state: BIState) -> str:
    return "END" if _blocked(state) else "analytics_agent"


def build_graph(deps: GraphDeps, *, guardrail_max_length: int = 2000):
    graph = StateGraph(BIState)

    graph.add_node("guardrail_agent", make_guardrail_node(guardrail_max_length))
    graph.add_node("intent_agent", make_intent_node(deps))
    graph.add_node("schema_agent", make_schema_node(deps))
    graph.add_node("sql_agent", make_sql_node(deps))
    graph.add_node("validate_agent", make_validate_node(deps))
    graph.add_node("execute_agent", make_execute_node(deps))
    graph.add_node("analytics_agent", make_analytics_node(deps))
    graph.add_node("viz_agent", make_viz_node(deps))
    graph.add_node("insight_agent", make_insight_node(deps))

    graph.set_entry_point("guardrail_agent")
    graph.add_conditional_edges(
        "guardrail_agent", _route_after_guardrail, {"intent_agent": "intent_agent", "END": END}
    )
    graph.add_edge("intent_agent", "schema_agent")
    graph.add_edge("schema_agent", "sql_agent")
    graph.add_edge("sql_agent", "validate_agent")
    graph.add_conditional_edges(
        "validate_agent", _route_after_validate, {"execute_agent": "execute_agent", "END": END}
    )
    graph.add_conditional_edges(
        "execute_agent", _route_after_execute, {"analytics_agent": "analytics_agent", "END": END}
    )
    graph.add_edge("analytics_agent", "viz_agent")
    graph.add_edge("viz_agent", "insight_agent")
    graph.add_edge("insight_agent", END)

    return graph.compile()
