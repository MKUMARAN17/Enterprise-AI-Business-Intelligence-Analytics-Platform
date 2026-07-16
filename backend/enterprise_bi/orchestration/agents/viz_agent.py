"""Agent 6 — Visualization Agent.

Chooses the best output format (table / line / bar / pie / scatter) from the
shape of the result and the user's phrasing, via :func:`bi_viz.select_visualization`,
and emits a Vega-Lite spec the frontend renders directly. The decision is
data-driven (column types + row count) plus intent-driven (the original question
as the ``request_hint``), satisfying "the AI selects the best visualization based
on both the user's request and the returned data."
"""
from __future__ import annotations

from bi_base.logging import get_logger
from bi_viz import Dataset as VizDataset
from bi_viz import select_visualization

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_viz_node(_deps: GraphDeps):
    def viz_node(state: BIState) -> dict:
        ds = VizDataset(
            columns=tuple(state.get("columns", [])),
            rows=tuple(tuple(r) for r in state.get("rows", [])),
        )
        choice = select_visualization(ds, request_hint=state.get("question", ""))
        log.info("agent.viz", kind=choice.kind)
        return {
            "visualization": {
                "kind": choice.kind,
                "reason": choice.reason,
                "spec": choice.spec,
                "x": choice.x,
                "y": choice.y,
            },
            "chart_kind": choice.kind,
        }

    return viz_node
