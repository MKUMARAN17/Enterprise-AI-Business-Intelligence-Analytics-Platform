# bi-reports

Report export for the enterprise AI BI platform.

`bi_reports` renders a query result (`Dataset`) to a downloadable file in CSV,
Excel or PDF.

## Why

Users need to take answers out of the platform — into a spreadsheet, a slide, an
email attachment. CSV is the universal baseline and is built on the standard
library, so it always works. Excel and PDF are richer formats that depend on
third-party engines; those are declared as **optional extras** and imported
lazily, so importing this package never requires the heavy libraries and a
CSV-only deployment stays lean.

When a requested engine is not installed the export **raises** rather than
degrading to a different format — a `.xlsx` file full of CSV bytes would be a
corrupt, misleading download.

## Runtime dependencies

None for CSV. Optional extras:

```bash
pip install 'bi-reports[excel]'   # openpyxl
pip install 'bi-reports[pdf]'     # reportlab
```

## Usage

```python
from bi_reports import Dataset, export

ds = Dataset(
    columns=("BRANCH", "TOTAL_SALES"),
    rows=(("North", 120), ("South", 90)),
)

result = export(ds, "csv", "/tmp/report.csv", title="Q1 sales")
result.format      # "csv"
result.engine      # "csv/stdlib"
result.byte_size   # real on-disk size in bytes
result.row_count   # 2
```

`export` also accepts `ExportFormat.EXCEL` / `ExportFormat.PDF`, and the
per-format helpers `export_csv`, `export_excel`, `export_pdf` are available
directly.

## Errors

- `ReportError` — base class for the whole layer.
- `MissingDependencyError` — the engine for the requested format is not
  installed.
- `UnsupportedFormatError` — the format string is not one of `csv`/`excel`/`pdf`.

## Development

```bash
pytest
```

Tests pass stdlib-only: the Excel/PDF paths assert the clean
`MissingDependencyError` when their libraries are absent, and assert a real file
is written when they are present.
