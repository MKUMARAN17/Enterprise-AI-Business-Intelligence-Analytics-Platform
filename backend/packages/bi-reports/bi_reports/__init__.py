"""bi_reports — export BI query results to CSV, Excel and PDF.

Fulfils the platform's file-export requirement: any answer (a
:class:`Dataset`) can be rendered to a downloadable file. CSV is always
available on the standard library; Excel (openpyxl) and PDF (reportlab) are
optional extras imported lazily, so importing this package never requires the
heavy dependencies and a CSV-only deployment stays lean.

Typical use::

    from bi_reports import Dataset, export

    ds = Dataset(columns=("BRANCH", "TOTAL_SALES"),
                 rows=(("North", 120), ("South", 90)))
    result = export(ds, "csv", "/tmp/report.csv", title="Q1 sales")
    result.byte_size  # real on-disk size
    result.engine     # "csv/stdlib"

Requesting a format whose engine is not installed raises
:class:`MissingDependencyError` (never a silently mis-typed file); an unknown
format raises :class:`UnsupportedFormatError`.
"""

from __future__ import annotations

from .errors import MissingDependencyError, ReportError, UnsupportedFormatError
from .exporters import (
    ExportFormat,
    ExportResult,
    export,
    export_csv,
    export_excel,
    export_pdf,
)
from .models import Dataset

__version__ = "0.1.0"

__all__ = [
    "Dataset",
    "ExportFormat",
    "ExportResult",
    "export",
    "export_csv",
    "export_excel",
    "export_pdf",
    "ReportError",
    "MissingDependencyError",
    "UnsupportedFormatError",
    "__version__",
]
