"""Exception hierarchy for :mod:`bi_reports`.

Export is the *last* step of answering a question: the data is already computed
and the user has asked for a file. The failure modes here are narrow and
operational — an unknown output format, or an optional engine (openpyxl,
reportlab) not being installed — and each must be reported crisply so the
platform can, for example, offer CSV when the Excel engine is absent instead of
silently handing back a file of the wrong type.

:class:`ReportError` subclasses :class:`RuntimeError` (not :class:`ValueError`)
to match the platform-wide convention that each subsystem's base error is a
``RuntimeError``, giving callers a single ``except`` to wrap the whole export
layer.
"""

from __future__ import annotations


class ReportError(RuntimeError):
    """Base class for every error raised by :mod:`bi_reports`.

    Catch this to treat the export layer as one failure domain.
    """


class MissingDependencyError(ReportError):
    """Raised when the engine required for a format is not importable.

    Excel and PDF export lean on third-party libraries (openpyxl, reportlab)
    that are *optional* extras. When the caller requests such a format but the
    library is absent we raise this rather than degrade to a different format:
    silently writing a ``.xlsx`` path with CSV bytes (or vice versa) would
    corrupt the download and mislead the user. The message names the missing
    package and the extra that provides it so the fix is obvious.
    """


class UnsupportedFormatError(ReportError):
    """Raised when an export format outside :class:`bi_reports.ExportFormat` is asked for.

    The supported formats are a small closed set (CSV/Excel/PDF). An unknown
    value is a caller error, so we fail fast rather than guess.
    """
