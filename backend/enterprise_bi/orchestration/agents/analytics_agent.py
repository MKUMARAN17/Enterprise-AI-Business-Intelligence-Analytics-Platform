"""Agent 5 — Analytics Agent.

Computes KPIs deterministically from the returned dataset (totals, averages,
period-over-period change, min/max, trend direction). This is done in Python, not
by the LLM — numbers must be exact and reproducible, and the insight agent then
*explains* these computed facts rather than inventing them. Keeping the maths out
of the model is what prevents fabricated percentages in the business summary.
"""
from __future__ import annotations

from bi_base.logging import get_logger
from bi_data import Dataset

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_analytics_node(_deps: GraphDeps):
    def analytics_node(state: BIState) -> dict:
        ds = Dataset(
            columns=tuple(state.get("columns", [])),
            rows=tuple(tuple(r) for r in state.get("rows", [])),
        )
        analytics = _compute(ds)
        log.info("agent.analytics", kpis=len(analytics.get("kpis", [])))
        return {"analytics": analytics}

    return analytics_node


def _compute(ds: Dataset) -> dict:
    if ds.is_empty:
        return {"kpis": [], "observations": ["No rows returned for this question."]}

    types = ds.column_types()
    numeric_cols = [c for c, t in types.items() if t == "numeric"]
    temporal_cols = [c for c, t in types.items() if t == "temporal"]
    categorical_cols = [c for c, t in types.items() if t == "categorical"]

    kpis: list[dict] = []
    observations: list[str] = []

    for col in numeric_cols:
        values = [v for v in ds.column_values(col) if isinstance(v, (int, float))]
        if not values:
            continue
        total = round(sum(values), 2)
        avg = round(total / len(values), 2)
        kpis.append(
            {"metric": col, "total": total, "average": avg, "max": max(values), "min": min(values)}
        )

    # Period-over-period on the first numeric column when a temporal axis exists.
    if temporal_cols and numeric_cols:
        change = _period_change(ds, temporal_cols[0], numeric_cols[0])
        if change is not None:
            observations.append(change)

    # Top category by the first numeric metric.
    if categorical_cols and numeric_cols:
        top = _top_category(ds, categorical_cols[0], numeric_cols[0])
        if top:
            observations.append(top)

    return {
        "kpis": kpis,
        "observations": observations,
        "dimensions": {"numeric": numeric_cols, "temporal": temporal_cols, "categorical": categorical_cols},
    }


def _period_change(ds: Dataset, tcol: str, ncol: str) -> str | None:
    ti, ni = ds.column_index(tcol), ds.column_index(ncol)
    series = sorted(
        ((r[ti], r[ni]) for r in ds.rows if r[ni] is not None), key=lambda x: str(x[0])
    )
    if len(series) < 2:
        return None
    first, last = series[0][1], series[-1][1]
    if not first:
        return None
    pct = round((last - first) / first * 100.0, 1)
    direction = "increased" if pct >= 0 else "decreased"
    return f"{ncol} {direction} {abs(pct)}% from {series[0][0]} to {series[-1][0]}."


def _top_category(ds: Dataset, ccol: str, ncol: str) -> str | None:
    ci, ni = ds.column_index(ccol), ds.column_index(ncol)
    agg: dict = {}
    for r in ds.rows:
        if r[ni] is None:
            continue
        agg[r[ci]] = agg.get(r[ci], 0) + r[ni]
    if not agg:
        return None
    top_key = max(agg, key=agg.get)
    total = sum(agg.values()) or 1
    share = round(agg[top_key] / total * 100.0, 1)
    return f"{top_key} leads on {ncol} with {share}% of the total."
