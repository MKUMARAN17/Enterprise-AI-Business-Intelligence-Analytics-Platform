"""Agent 7 — Insight Agent.

Turns the *computed* analytics (from the Analytics Agent) plus a compact preview
of the rows into a business-language explanation: a summary, highlights, and
recommendations — "instead of only showing numbers, the AI explains possible
business reasons." The model is given the exact KPIs/observations to ground its
prose, so it explains real numbers rather than inventing them. Falls back to a
deterministic summary built from the analytics if the LLM step errors, so a turn
always returns a usable narrative.
"""
from __future__ import annotations

from bi_base.errors import AgentError
from bi_base.logging import get_logger

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_insight_node(deps: GraphDeps):
    def insight_node(state: BIState) -> dict:
        analytics = state.get("analytics", {})
        preview = _preview(state)
        try:
            result = deps.router.run(
                "insight",
                question=state["question"],
                kpis=str(analytics.get("kpis", [])),
                observations=" ".join(analytics.get("observations", [])),
                preview=preview,
            )
        except AgentError:
            log.warning("agent.insight_fallback")
            result = _fallback(analytics, state.get("row_count", 0))
        return {"insight": result}

    return insight_node


def _preview(state: BIState, limit: int = 8) -> str:
    cols = state.get("columns", [])
    rows = state.get("rows", [])[:limit]
    lines = [" | ".join(str(c) for c in cols)]
    lines += [" | ".join(str(v) for v in r) for r in rows]
    return "\n".join(lines)


def _fallback(analytics: dict, row_count: int) -> dict:
    obs = analytics.get("observations", [])
    summary = (
        obs[0]
        if obs
        else f"Query returned {row_count} row(s)."
    )
    return {"summary": summary, "highlights": obs, "recommendations": []}
