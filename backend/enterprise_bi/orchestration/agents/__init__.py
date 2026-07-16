"""The seven BI agents (+ guardrail & execute nodes) as LangGraph node factories.

Each ``make_*_node(deps)`` returns a closure ``(BIState) -> dict`` that the graph
builder wires in order. Factories (not bare functions) so the collaborators are
injected once at boot and the nodes stay pure/testable.
"""
from __future__ import annotations

from enterprise_bi.orchestration.agents.analytics_agent import make_analytics_node
from enterprise_bi.orchestration.agents.execute_agent import make_execute_node
from enterprise_bi.orchestration.agents.guardrail_agent import make_guardrail_node
from enterprise_bi.orchestration.agents.insight_agent import make_insight_node
from enterprise_bi.orchestration.agents.intent_agent import make_intent_node
from enterprise_bi.orchestration.agents.schema_agent import make_schema_node
from enterprise_bi.orchestration.agents.sql_agent import make_sql_node
from enterprise_bi.orchestration.agents.validate_agent import make_validate_node
from enterprise_bi.orchestration.agents.viz_agent import make_viz_node

__all__ = [
    "make_guardrail_node",
    "make_intent_node",
    "make_schema_node",
    "make_sql_node",
    "make_validate_node",
    "make_execute_node",
    "make_analytics_node",
    "make_viz_node",
    "make_insight_node",
]
