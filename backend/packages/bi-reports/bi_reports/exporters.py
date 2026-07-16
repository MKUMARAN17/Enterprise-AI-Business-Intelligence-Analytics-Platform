"""Export a :class:`bi_reports.Dataset` to CSV, Excel or PDF.

The platform lets users download any answer as a file. CSV is the universal
baseline and is implemented on the standard-library :mod:`csv` module, so it
*always* works with no extra install. Excel and PDF are richer formats that
depend on third-party engines (openpyxl, reportlab); those libraries are
declared as optional extras and imported **lazily inside the export function**
so that:

* importing :mod:`bi_reports` never fails just because a heavy optional library
  is missing, and
* a deployment that only needs CSV pays no import cost for the others.

When a requested engine is unavailable we raise
:class:`MissingDependencyError` rather than degrade to a different format — a
``.xlsx`` file containing CSV bytes would be a corrupt, misleading download.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from enum import StrEnum

from .errors import MissingDependencyError, UnsupportedFormatError
from .models import Dataset


class ExportFormat(StrEnum):
    """Supported export formats.

    Subclasses ``str`` so members compare/serialise as their plain value
    (``"csv"``), which lets callers pass either the enum or the bare string
    through :func:`export` interchangeably and lets the value survive JSON
    round-trips in an API payload.
    """

    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"


@dataclass(frozen=True, slots=True)
class ExportResult:
    """The outcome of a successful export.

    Attributes
    ----------
    format:
        The format actually written (``ExportFormat`` value string).
    path:
        Absolute or caller-supplied path the file was written to.
    byte_size:
        Real on-disk size in bytes, read back after writing — a cheap integrity
        signal the caller can log or surface ("your 3.2 kB report is ready").
    row_count:
        Number of data rows written (excludes the header).
    engine:
        Which backend produced the file (``"csv/stdlib"``, ``"openpyxl"``,
        ``"reportlab"``). Recorded for observability so support can tell how a
        given file was generated.
    """

    format: str
    path: str
    byte_size: int
    row_count: int
    engine: str


def _coerce_format(fmt: str | ExportFormat) -> ExportFormat:
    """Normalise ``fmt`` to an :class:`ExportFormat`, or raise for unknown values.

    Accepts an ``ExportFormat`` as-is and a case-insensitive string otherwise so
    ``"CSV"``, ``"csv"`` and ``ExportFormat.CSV`` are all valid inputs.
    """
    if isinstance(fmt, ExportFormat):
        return fmt
    if isinstance(fmt, str):
        try:
            return ExportFormat(fmt.strip().lower())
        except ValueError:
            pass
    supported = ", ".join(f.value for f in ExportFormat)
    raise UnsupportedFormatError(f"unsupported export format {fmt!r}; expected one of: {supported}")


def _cell_to_text(value: object) -> str:
    """Render a cell for text-based formats (CSV/PDF).

    ``None`` becomes an empty string (the conventional CSV representation of a
    NULL); everything else defers to ``str``. Numbers keep their natural
    repr — we intentionally do not localise or thousands-separate here so CSV
    stays machine-parseable.
    """
    return "" if value is None else str(value)


def export_csv(dataset: Dataset, path: str, *, title: str = "") -> ExportResult:
    """Write ``dataset`` to ``path`` as UTF-8 CSV using the standard library.

    ``title`` is accepted for signature symmetry with the other exporters but is
    intentionally *not* written into the body: injecting a title row would shift
    the header off row 1 and break naive CSV parsers/``pandas.read_csv`` callers.
    The header row is always the column names; one row follows per data row.

    ``newline=""`` is required by :mod:`csv` to avoid doubled line endings on
    Windows. Always succeeds (no optional dependency).
    """
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(dataset.columns)
        for row in dataset.rows:
            writer.writerow([_cell_to_text(v) for v in row])

    return ExportResult(
        format=ExportFormat.CSV.value,
        path=path,
        byte_size=os.path.getsize(path),
        row_count=dataset.row_count,
        engine="csv/stdlib",
    )


def export_excel(dataset: Dataset, path: str, *, title: str = "") -> ExportResult:
    """Write ``dataset`` to ``path`` as a ``.xlsx`` workbook via openpyxl.

    openpyxl is imported lazily so the dependency is only required when Excel is
    actually requested; if it is not installed we raise
    :class:`MissingDependencyError` with an actionable message pointing at the
    ``excel`` extra. The header is written as the first row; numeric cells are
    written as their native numeric type so Excel treats them as numbers (right
    aligned, sortable) rather than text.
    """
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover - exercised only when lib absent
        raise MissingDependencyError(
            "Excel export requires 'openpyxl'. Install the optional extra: "
            "pip install 'bi-reports[excel]'"
        ) from exc

    workbook = Workbook()
    sheet = workbook.active
    # Excel sheet titles are capped at 31 chars and forbid a handful of
    # characters; fall back to a safe default when no usable title is given.
    sheet.title = (title[:31] if title else "Report") or "Report"

    sheet.append(list(dataset.columns))
    for row in dataset.rows:
        # openpyxl accepts native scalars; pass numbers through unchanged and
        # coerce everything else (dates-as-strings, categoricals) to text.
        cells = [
            value if isinstance(value, (int, float)) and not isinstance(value, bool) else _none_to_blank(value)
            for value in row
        ]
        sheet.append(cells)

    workbook.save(path)

    return ExportResult(
        format=ExportFormat.EXCEL.value,
        path=path,
        byte_size=os.path.getsize(path),
        row_count=dataset.row_count,
        engine="openpyxl",
    )


def _none_to_blank(value: object) -> object:
    """Map ``None`` to an empty cell; leave other values untouched."""
    return "" if value is None else value


def export_pdf(dataset: Dataset, path: str, *, title: str = "") -> ExportResult:
    """Write ``dataset`` to ``path`` as a tabular PDF via reportlab.

    reportlab is imported lazily; absent it we raise
    :class:`MissingDependencyError` pointing at the ``pdf`` extra rather than
    emit a non-PDF file. The dataset is laid out as a bordered table with a
    header row (and an optional ``title`` paragraph above it) using reportlab's
    high-level ``platypus`` API, which handles pagination for large results.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:  # pragma: no cover - exercised only when lib absent
        raise MissingDependencyError(
            "PDF export requires 'reportlab'. Install the optional extra: "
            "pip install 'bi-reports[pdf]'"
        ) from exc

    document = SimpleDocTemplate(path, pagesize=landscape(letter))
    flowables: list = []

    if title:
        styles = getSampleStyleSheet()
        flowables.append(Paragraph(title, styles["Title"]))
        flowables.append(Spacer(1, 12))

    table_data: list[list[str]] = [list(dataset.columns)]
    table_data.extend([[_cell_to_text(v) for v in row] for row in dataset.rows])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    flowables.append(table)
    document.build(flowables)

    return ExportResult(
        format=ExportFormat.PDF.value,
        path=path,
        byte_size=os.path.getsize(path),
        row_count=dataset.row_count,
        engine="reportlab",
    )


# Dispatch table: format -> concrete exporter. Kept as data so :func:`export`
# stays a thin, obviously-correct router with no branching to drift.
_EXPORTERS = {
    ExportFormat.CSV: export_csv,
    ExportFormat.EXCEL: export_excel,
    ExportFormat.PDF: export_pdf,
}


def export(
    dataset: Dataset,
    fmt: str | ExportFormat,
    path: str,
    *,
    title: str = "",
) -> ExportResult:
    """Export ``dataset`` to ``path`` in ``fmt``.

    The single entry point the platform calls. ``fmt`` may be an
    :class:`ExportFormat` or a (case-insensitive) string. Unknown formats raise
    :class:`UnsupportedFormatError`; a format whose engine is not installed
    raises :class:`MissingDependencyError`. On success the file exists at
    ``path`` and the returned :class:`ExportResult` reports its real byte size.
    """
    resolved = _coerce_format(fmt)
    exporter = _EXPORTERS[resolved]
    return exporter(dataset, path, title=title)
