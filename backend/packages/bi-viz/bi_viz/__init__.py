"""bi_viz — automatic visualization selection for BI query results.

Given the *shape* of a query result (:class:`Dataset`) plus a light hint about
the user's intent, :func:`select_visualization` chooses the chart that best
communicates the answer — table, line, bar, pie or scatter — and returns a
ready-to-render Vega-Lite v5 spec inside a :class:`VizChoice`.

The package is pure standard library at runtime: it emits JSON-serialisable
spec ``dict`` objects and leaves rendering to the frontend, so it has no chart
library dependency of its own.

Typical use::

    from bi_viz import Dataset, select_visualization

    ds = Dataset(columns=("BRANCH", "TOTAL_SALES"),
                 rows=(("North", 120), ("South", 90)))
    choice = select_visualization(ds, request_hint="top branches by sales")
    choice.kind   # -> "bar"
    choice.spec   # -> {... Vega-Lite v5 ...}
"""

from __future__ import annotations

from .errors import UnknownChartKindError, VizError
from .models import Dataset, VizChoice
from .selector import select_visualization
from .specs import build_chart_spec

__version__ = "0.1.0"

__all__ = [
    "Dataset",
    "VizChoice",
    "VizError",
    "UnknownChartKindError",
    "select_visualization",
    "build_chart_spec",
    "__version__",
]
