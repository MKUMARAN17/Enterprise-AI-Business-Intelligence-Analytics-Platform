"""Exception hierarchy for :mod:`bi_viz`.

Visualization selection sits *after* a query has already succeeded: by the time
we are choosing a chart, the expensive work (SQL generation, execution) is done.
A failure here should therefore be rare and almost always a programming error
(an unknown chart kind, a malformed request) rather than a user-facing data
problem. We still model failures as typed exceptions so the surrounding platform
can distinguish "could not visualise" from "query failed" and fall back to a raw
table instead of surfacing a stack trace.

:class:`VizError` subclasses :class:`RuntimeError` (not :class:`ValueError`) to
stay consistent with the rest of the platform's packages, where the base error
of every subsystem is a ``RuntimeError`` so a caller can wrap a whole layer in a
single ``except``.
"""

from __future__ import annotations


class VizError(RuntimeError):
    """Base class for every error raised by :mod:`bi_viz`.

    Catch this to treat the visualization layer as a single failure domain and
    degrade gracefully (e.g. render the result as a plain table instead).
    """


class UnknownChartKindError(VizError):
    """Raised when a chart ``kind`` outside the supported set is requested.

    The supported kinds are intentionally a small, closed vocabulary
    (``table``/``line``/``bar``/``pie``/``scatter``) because each maps to a
    specific Vega-Lite mark + encoding template. An unknown kind almost always
    means a caller typo or a spec drift, so we fail loudly rather than emit an
    empty or nonsensical Vega-Lite document.
    """
