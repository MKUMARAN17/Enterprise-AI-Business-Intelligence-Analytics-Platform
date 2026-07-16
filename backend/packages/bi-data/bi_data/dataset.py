"""The canonical query-result value passed between layers.

``Dataset`` is the single hand-off shape from the data layer to analytics /
visualization / reporting. It is deliberately primitive (column names + row
tuples) so it serialises cleanly to JSON on the wire and every downstream package
can define a structurally-identical local copy without importing bi-data. Column
names stay UPPERCASE, matching the DB and the generated SQL.

``column_types`` performs light type inference (numeric / temporal / categorical)
which the visualization agent uses to pick a chart and the insight agent uses to
decide which columns to summarise.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Dataset:
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def is_empty(self) -> bool:
        return len(self.rows) == 0 or len(self.columns) == 0

    def column_index(self, name: str) -> int:
        return self.columns.index(name.upper())

    def column_values(self, name: str) -> list:
        idx = self.column_index(name)
        return [r[idx] for r in self.rows]

    def to_records(self) -> list[dict]:
        """Row tuples → list of dicts keyed by column name (for JSON / Vega)."""
        return [dict(zip(self.columns, r, strict=False)) for r in self.rows]

    def column_types(self) -> dict[str, str]:
        """Infer 'numeric' | 'temporal' | 'categorical' per column."""
        types: dict[str, str] = {}
        for i, col in enumerate(self.columns):
            values = [r[i] for r in self.rows if i < len(r) and r[i] is not None]
            types[col] = _infer_type(col, values)
        return types


def _infer_type(column: str, values: list) -> str:
    upper = column.upper()
    if upper.endswith(("_DATE", "_MONTH", "_PERIOD", "_YEAR")) or upper in {"MONTH", "PERIOD"}:
        return "temporal"
    if not values:
        return "categorical"
    if all(isinstance(v, bool) is False and isinstance(v, (int, float)) for v in values):
        return "numeric"
    if all(isinstance(v, (_dt.date, _dt.datetime)) for v in values):
        return "temporal"
    # 'YYYY-MM' / ISO date strings → temporal
    if all(isinstance(v, str) and _looks_temporal(v) for v in values):
        return "temporal"
    return "categorical"


def _looks_temporal(s: str) -> bool:
    s = s.strip()
    if len(s) == 7 and s[4] == "-" and s[:4].isdigit() and s[5:].isdigit():
        return True  # 'YYYY-MM'
    try:
        _dt.date.fromisoformat(s[:10])
        return True
    except ValueError:
        return False
