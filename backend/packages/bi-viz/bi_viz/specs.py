"""Vega-Lite v5 spec construction for :mod:`bi_viz`.

We emit Vega-Lite (rather than a bespoke chart JSON) because it is a stable,
widely-implemented grammar: the frontend can render the spec with ``vega-embed``
untouched, and downstream tooling can reason about the ``mark``/``encoding``
without knowing anything about this package. Each chart ``kind`` maps to exactly
one mark + encoding template so the output is predictable and diff-friendly.

Data is inlined as ``data.values`` (a list of row dicts). For the modest result
sets a BI answer returns this keeps the spec self-contained — no second fetch,
no server-side data endpoint to coordinate — which matters when the spec is
handed to the client as part of a single answer payload.
"""

from __future__ import annotations

from .errors import UnknownChartKindError
from .models import Dataset

_VEGA_LITE_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"

# The closed vocabulary of chart kinds this package can emit. Anything else is a
# programming error surfaced via :class:`UnknownChartKindError`.
SUPPORTED_KINDS: frozenset[str] = frozenset({"table", "line", "bar", "pie", "scatter"})

# Vega-Lite channel encoding *type* per selected axis role. We choose the
# encoding type from the chart kind rather than re-inferring it so the mark and
# its axes always agree (e.g. a bar's category axis is always nominal).
_LINE_X_TYPE = "temporal"
_QUANTITATIVE = "quantitative"
_NOMINAL = "nominal"


def _rows_as_dicts(dataset: Dataset) -> list[dict]:
    """Materialise rows as ``{column: value}`` dicts for ``data.values``.

    Field names are the raw (UPPERCASE) column names so they match the field
    references used in the encoding block below without any translation layer.
    """
    columns = dataset.columns
    return [dict(zip(columns, row, strict=False)) for row in dataset.rows]


def build_chart_spec(
    kind: str,
    dataset: Dataset,
    x: str | None,
    y: str | None,
    title: str = "",
) -> dict:
    """Build a complete Vega-Lite v5 spec for ``kind`` over ``dataset``.

    Parameters
    ----------
    kind:
        One of :data:`SUPPORTED_KINDS`.
    dataset:
        The data to inline into ``data.values``.
    x, y:
        Field names for the primary axes. Required for every chart kind except
        ``table`` (which renders raw rows and needs no encoding). Passing a
        field absent from ``dataset.columns`` is allowed — the spec still
        references it — but for the non-table kinds both must be non-``None``.
    title:
        Optional chart title; omitted from the spec when empty.

    Raises
    ------
    UnknownChartKindError
        If ``kind`` is not supported.
    VizError
        If a non-table kind is requested without both ``x`` and ``y``.
    """
    if kind not in SUPPORTED_KINDS:
        raise UnknownChartKindError(
            f"unsupported chart kind {kind!r}; expected one of {sorted(SUPPORTED_KINDS)}"
        )

    spec: dict = {"$schema": _VEGA_LITE_SCHEMA, "data": {"values": _rows_as_dicts(dataset)}}
    if title:
        spec["title"] = title

    if kind == "table":
        # Vega-Lite has no native table mark; a "table" is our signal that the
        # result is best shown as raw rows. We still emit the data so a client
        # can render it, and tag the spec via ``usermeta`` so the frontend can
        # route it to a grid component instead of vega-embed.
        spec["usermeta"] = {"bi_viz": {"render": "table"}}
        return spec

    # Every remaining kind is a real chart and needs two axis fields.
    if x is None or y is None:
        from .errors import VizError

        raise VizError(f"chart kind {kind!r} requires both x and y (got x={x!r}, y={y!r})")

    if kind == "line":
        spec["mark"] = {"type": "line", "point": True}
        spec["encoding"] = {
            "x": {"field": x, "type": _LINE_X_TYPE},
            "y": {"field": y, "type": _QUANTITATIVE},
        }
    elif kind == "bar":
        spec["mark"] = "bar"
        spec["encoding"] = {
            # Sort the category axis by the measure descending: a bar chart born
            # from a "top / rank" intent should read as a ranking, not appear in
            # arbitrary row order.
            "x": {"field": x, "type": _NOMINAL, "sort": "-y"},
            "y": {"field": y, "type": _QUANTITATIVE},
        }
    elif kind == "pie":
        spec["mark"] = {"type": "arc"}
        spec["encoding"] = {
            "theta": {"field": y, "type": _QUANTITATIVE},
            "color": {"field": x, "type": _NOMINAL},
        }
    elif kind == "scatter":
        spec["mark"] = {"type": "point"}
        spec["encoding"] = {
            "x": {"field": x, "type": _QUANTITATIVE},
            "y": {"field": y, "type": _QUANTITATIVE},
        }

    return spec
