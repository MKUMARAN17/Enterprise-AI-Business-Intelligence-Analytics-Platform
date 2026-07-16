"""Core data shapes for :mod:`bi_reports`.

Like its sibling :mod:`bi_viz`, this package keeps a *local* copy of
:class:`Dataset` instead of importing it from another package. Both packages
consume the same "query result" shape, but they are independent leaf packages
and a cross-import would tie their build/release cycles together for the sake of
a tiny, stable value object. Duplication is the cheaper trade-off.

For export, the :meth:`Dataset.column_types` inference is used to decide cell
formatting (right-aligning numbers, formatting temporal columns) so the exported
file reads the way a human expects, not just as raw text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

_TEMPORAL_SUFFIXES: tuple[str, ...] = ("_DATE", "_MONTH", "_PERIOD")
_TEMPORAL_NAMES: frozenset[str] = frozenset({"DATE", "MONTH", "PERIOD"})


def _parses_as_iso_temporal(value: object) -> bool:
    """Return ``True`` when ``value`` is a string parseable as an ISO date/time.

    Only strings are considered: numbers are covered by the numeric branch, and
    reading a bare integer as a date would be a false positive. ``date`` and
    ``datetime`` ``fromisoformat`` together cover the shapes MySQL emits.
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
    """An immutable, DB-shaped query result to be exported.

    Attributes
    ----------
    columns:
        UPPERCASE column names in select order; used verbatim as the header row
        of every export format.
    rows:
        Row tuples positionally aligned with ``columns``; cell values are
        ``str``/``int``/``float``/``None``.

    ``frozen``/``slots`` make it hashable and cheap to pass around the export
    pipeline without defensive copies.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple, ...]

    @property
    def row_count(self) -> int:
        """Number of data rows (excludes the header)."""
        return len(self.rows)

    @property
    def is_empty(self) -> bool:
        """``True`` when there are no data rows.

        An empty dataset is still exportable — the file will contain just the
        header row — so callers get a valid, if empty, download.
        """
        return self.row_count == 0

    def _column_values(self, index: int) -> list[object]:
        """Non-null values of the column at ``index`` (type tests ignore nulls)."""
        return [row[index] for row in self.rows if index < len(row) and row[index] is not None]

    def column_types(self) -> dict[str, str]:
        """Infer ``{column: "numeric"|"temporal"|"categorical"}`` in column order.

        Test order (first match wins):

        1. **temporal** — name ends in ``_DATE``/``_MONTH``/``_PERIOD`` (or is
           exactly ``DATE``/``MONTH``/``PERIOD``), or all observed values parse
           as ISO date/time.
        2. **numeric** — at least one observed value and all observed values are
           ``int``/``float`` (excluding ``bool``, which is a flag).
        3. **categorical** — everything else, including all-``NULL`` columns.
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
