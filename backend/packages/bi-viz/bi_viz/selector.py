"""Automatic chart selection for :mod:`bi_viz`.

The problem this solves: a natural-language BI answer returns a table of numbers,
but a bare table is a poor default for a human reader. Given *only* the shape of
the result and a light-weight hint about the user's intent, this module picks the
chart that communicates the answer best, and emits a ready-to-render Vega-Lite
spec.

Design principles:

* **Shape first, intent second.** The inferred column types (from
  :meth:`bi_viz.Dataset.column_types`) constrain what is even *possible* — you
  cannot draw a line without a time axis. The ``request_hint`` only disambiguates
  among the charts a given shape permits.
* **Deterministic and explainable.** The rules are a fixed, ordered cascade and
  every branch records a ``reason``. There is no scoring model to drift; the same
  input always yields the same chart, which is essential for testing and for
  users who re-run a question.
* **Table is the safe fallback.** When no rule fires we return a table rather
  than force an inappropriate chart — showing the data plainly always beats
  showing it misleadingly.
"""

from __future__ import annotations

import re

from .models import Dataset, VizChoice
from .specs import build_chart_spec

# Intent keywords. Kept as module-level constants so the vocabulary is visible in
# one place and easy to extend without touching the decision logic.
_TREND_KEYWORDS: tuple[str, ...] = ("trend", "over time", "monthly", "month over month", "time series")
_COMPARE_KEYWORDS: tuple[str, ...] = ("compare", "comparison", "top", "rank", "ranking", "highest", "lowest", "most", "least")
_PROPORTION_KEYWORDS: tuple[str, ...] = ("proportion", "share", "percentage", "percent", "distribution", "breakdown", "split")

# "last N months/weeks/quarters/..." is a trend request even without the literal
# word "trend"; match it structurally.
_LAST_N_PERIODS = re.compile(r"\blast\s+\d+\s+(day|week|month|quarter|year)s?\b", re.IGNORECASE)

# Rough upper bound on pie slices. Beyond a dozen categories a pie is unreadable
# and a bar communicates the same proportions far better, so we redirect.
_MAX_PIE_SLICES = 12


def _mentions(hint: str, keywords: tuple[str, ...]) -> bool:
    """Return ``True`` if any keyword appears in the already-lowercased ``hint``."""
    return any(keyword in hint for keyword in keywords)


def _top_n_dataset(dataset: Dataset, y: str, top_n: int) -> Dataset:
    """Return a copy of ``dataset`` reduced to its ``top_n`` rows by ``y`` desc.

    Applied for ranking bar charts so a "top 5 branches" hint actually ships five
    bars. Rows whose measure is non-numeric or ``None`` sort last (treated as
    ``-inf``) rather than raising, keeping selection total.
    """
    if top_n <= 0:
        return dataset
    y_index = dataset.columns.index(y)

    def sort_key(row: tuple) -> float:
        value = row[y_index] if y_index < len(row) else None
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float("-inf")

    ranked = sorted(dataset.rows, key=sort_key, reverse=True)[:top_n]
    return Dataset(columns=dataset.columns, rows=tuple(ranked))


def select_visualization(
    dataset: Dataset,
    request_hint: str = "",
    top_n: int | None = None,
) -> VizChoice:
    """Choose the best chart for ``dataset`` given an optional intent ``hint``.

    The decision cascade (first match wins):

    1. **Empty result or a single column** → ``table``. There is nothing to plot
       on two axes.
    2. **Trend intent + a temporal column** → ``line`` (x = the temporal column,
       y = the first numeric column). Time series are the one case where intent
       and shape align so strongly that we lead with it.
    3. **Compare/top/rank intent + exactly one categorical and one numeric
       column** → ``bar`` (x = category, y = measure), optionally truncated to
       ``top_n`` rows sorted by the measure.
    4. **Proportion/share intent + exactly one categorical and one numeric
       column** → ``pie`` when there are at most ~12 categories; with more
       categories a pie is unreadable so we fall back to ``bar``.
    5. **Two numeric columns and no temporal column** → ``scatter`` to expose
       correlation.
    6. **Otherwise** → ``table``, the always-correct fallback.

    Parameters
    ----------
    dataset:
        The query result to visualise.
    request_hint:
        Free-text describing what the user asked for (e.g. the original question).
        Matched case-insensitively against small keyword sets; empty is fine and
        simply means the choice is driven by shape alone.
    top_n:
        When a bar chart is chosen, limit it to this many highest bars. Ignored
        for other kinds.
    """
    hint = request_hint.lower()
    types = dataset.column_types()
    numeric_cols = [name for name, kind in types.items() if kind == "numeric"]
    temporal_cols = [name for name, kind in types.items() if kind == "temporal"]
    categorical_cols = [name for name, kind in types.items() if kind == "categorical"]

    # Rule 1: nothing to plot.
    if dataset.is_empty or len(dataset.columns) <= 1:
        reason = "empty result" if dataset.is_empty else "single column — no second axis to plot"
        return VizChoice(
            kind="table",
            reason=f"table: {reason}.",
            spec=build_chart_spec("table", dataset, None, None),
            x=None,
            y=None,
        )

    wants_trend = _mentions(hint, _TREND_KEYWORDS) or bool(_LAST_N_PERIODS.search(hint))
    wants_compare = _mentions(hint, _COMPARE_KEYWORDS)
    wants_proportion = _mentions(hint, _PROPORTION_KEYWORDS)
    is_one_cat_one_num = len(categorical_cols) == 1 and len(numeric_cols) == 1

    # Rule 2: time-series line.
    if wants_trend and temporal_cols and numeric_cols:
        x, y = temporal_cols[0], numeric_cols[0]
        return VizChoice(
            kind="line",
            reason=f"line: trend intent with temporal column {x!r} and measure {y!r}.",
            spec=build_chart_spec("line", dataset, x, y),
            x=x,
            y=y,
        )

    # Rule 3: ranked / comparison bar.
    if wants_compare and is_one_cat_one_num:
        x, y = categorical_cols[0], numeric_cols[0]
        data = dataset
        limit_note = ""
        if top_n is not None and top_n > 0:
            data = _top_n_dataset(dataset, y, top_n)
            limit_note = f" (top {top_n})"
        return VizChoice(
            kind="bar",
            reason=f"bar: comparison intent across category {x!r} by measure {y!r}{limit_note}.",
            spec=build_chart_spec("bar", data, x, y),
            x=x,
            y=y,
        )

    # Rule 4: proportion pie (or bar when there are too many slices).
    if wants_proportion and is_one_cat_one_num:
        x, y = categorical_cols[0], numeric_cols[0]
        if dataset.row_count <= _MAX_PIE_SLICES:
            return VizChoice(
                kind="pie",
                reason=f"pie: proportion intent over {dataset.row_count} categories of {x!r} by {y!r}.",
                spec=build_chart_spec("pie", dataset, x, y),
                x=x,
                y=y,
            )
        return VizChoice(
            kind="bar",
            reason=(
                f"bar: proportion intent but {dataset.row_count} categories exceed the "
                f"{_MAX_PIE_SLICES}-slice pie limit — a bar reads better."
            ),
            spec=build_chart_spec("bar", dataset, x, y),
            x=x,
            y=y,
        )

    # Rule 5: correlation scatter.
    if len(numeric_cols) >= 2 and not temporal_cols:
        x, y = numeric_cols[0], numeric_cols[1]
        return VizChoice(
            kind="scatter",
            reason=f"scatter: two numeric columns {x!r} and {y!r} with no time axis.",
            spec=build_chart_spec("scatter", dataset, x, y),
            x=x,
            y=y,
        )

    # Rule 6: safe fallback.
    return VizChoice(
        kind="table",
        reason="table: no chart heuristic matched the result shape and intent.",
        spec=build_chart_spec("table", dataset, None, None),
        x=None,
        y=None,
    )
