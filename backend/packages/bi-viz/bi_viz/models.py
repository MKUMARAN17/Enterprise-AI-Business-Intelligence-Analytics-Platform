"""Core data shapes for :mod:`bi_viz`.

This module deliberately owns a *local* copy of :class:`Dataset` rather than
importing it from a sibling package. The two visualization/reporting packages
share the same conceptual "query result" shape, but coupling them at import time
would create a dependency edge between two otherwise-independent leaf packages —
a change to one would force a rebuild/redeploy of the other. Duplicating a tiny,
stable value object is the cheaper trade-off.

``Dataset`` is the single input to the whole package: every heuristic in
:mod:`bi_viz.selector` reasons purely about its *shape* (how many columns, of
what inferred type) and never about the semantics of individual values, which is
what makes chart selection deterministic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

# Columns whose *name* implies a time axis. We treat the name as authoritative
# because a column called ``SALE_MONTH`` is temporal even when its values happen
# to be stored as integers (e.g. ``202401``) that would otherwise infer numeric.
_TEMPORAL_SUFFIXES: tuple[str, ...] = ("_DATE", "_MONTH", "_PERIOD")
_TEMPORAL_NAMES: frozenset[str] = frozenset({"DATE", "MONTH", "PERIOD"})


def _parses_as_iso_temporal(value: object) -> bool:
    """Return ``True`` when ``value`` is a string that parses as an ISO date/time.

    We only attempt string parsing: ints/floats are handled by the numeric
    branch of :meth:`Dataset.column_types`, and treating a bare integer like
    ``2024`` as a "date" would be a false positive. ``date.fromisoformat`` and
    ``datetime.fromisoformat`` between them cover the ``YYYY-MM-DD`` and
    ``YYYY-MM-DDTHH:MM:SS`` shapes MySQL emits for ``DATE``/``DATETIME`` columns.
    """
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate:
        return False
    for parser in (date.fromisoformat, datetime.fromisoformat):
        try:
            parser(candidate)
        except ValueError:
            continue
        else:
            return True
    return False


@dataclass(frozen=True, slots=True)
class Dataset:
    """An immutable, DB-shaped query result.

    Attributes
    ----------
    columns:
        Column names in select order. They are expected to be UPPERCASE to
        match the database, and are used verbatim as Vega-Lite field names so
        the emitted spec lines up with the row dictionaries.
    rows:
        Row tuples positionally aligned with ``columns``. Cell values are the
        JSON-friendly scalars a driver returns: ``str``/``int``/``float``/``None``.

    The class is ``frozen``/``slots`` so it is hashable, cheap, and safe to
    share across the request-handling pipeline without defensive copies.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple, ...]

    @property
    def row_count(self) -> int:
        """Number of data rows (never counts the header)."""
        return len(self.rows)

    @property
    def is_empty(self) -> bool:
        """``True`` when there are no data rows.

        Emptiness is defined by rows, not columns: a query can legitimately
        return a well-defined column list with zero matching rows, and the
        selector treats that as "nothing to chart — show a table".
        """
        return self.row_count == 0

    def _column_values(self, index: int) -> list[object]:
        """Return the non-null values of the column at ``index``.

        Null-stripping is centralised here because every type test ("all
        numeric", "all temporal") is defined over *observed* values only; a
        column that is entirely ``NULL`` carries no type signal and falls back
        to categorical.
        """
        return [row[index] for row in self.rows if index < len(row) and row[index] is not None]

    def column_types(self) -> dict[str, str]:
        """Infer a coarse semantic type per column.

        Returns a mapping ``{column_name: "numeric"|"temporal"|"categorical"}``
        preserving column order. The order of the tests matters:

        1. **temporal** — the column *name* ends in ``_DATE``/``_MONTH``/
           ``_PERIOD`` (or is exactly ``DATE``/``MONTH``/``PERIOD``), *or* every
           observed value parses as an ISO date/time. Name wins first because a
           period key stored as an integer must still land on the time axis.
        2. **numeric** — there is at least one observed value and every observed
           value is an ``int``/``float`` (``bool`` is excluded: it is a flag,
           not a measure).
        3. **categorical** — everything else, including all-``NULL`` columns,
           which carry no type signal.
        """
        types: dict[str, str] = {}
        for index, name in enumerate(self.columns):
            upper = name.upper()
            values = self._column_values(index)

            name_is_temporal = upper.endswith(_TEMPORAL_SUFFIXES) or upper in _TEMPORAL_NAMES
            if name_is_temporal or (values and all(_parses_as_iso_temporal(v) for v in values)):
                types[name] = "temporal"
                continue

            if values and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                types[name] = "numeric"
                continue

            types[name] = "categorical"
        return types


@dataclass(frozen=True, slots=True)
class VizChoice:
    """The decision produced by :func:`bi_viz.select_visualization`.

    Bundles the *what* (``kind``), the *why* (``reason``, a human-readable
    justification we surface in logs and UI tooltips so the automatic choice is
    auditable), the *ready-to-render* Vega-Lite v5 ``spec``, and the chosen
    axis fields (``x``/``y``) so callers can re-label or override without having
    to re-parse the spec.
    """

    kind: str
    reason: str
    spec: dict
    x: str | None
    y: str | None
