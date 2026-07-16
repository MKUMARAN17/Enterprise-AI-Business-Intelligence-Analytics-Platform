"""bi_sql_guard — fail-closed validation of LLM-generated SQL.

This package is the security boundary between a natural-language-to-SQL layer
and the database. It statically validates that a query is read-only
(SELECT / WITH CTE only), contains no destructive or exfiltration constructs,
references only tables the caller's role may read, and carries a bounded
``LIMIT``.

Typical usage::

    from bi_sql_guard import SqlGuard

    guard = SqlGuard(allowed_tables={"ORDERS", "CUSTOMERS"}, max_limit=1000)
    result = guard.validate(llm_sql)   # raises on any violation (fail-closed)
    run(result.normalized_sql)

For a non-raising API use :meth:`SqlGuard.try_validate`, which returns a
:class:`GuardResult` with ``ok=False`` instead of raising.
"""

from __future__ import annotations

from .errors import (
    DestructiveStatementError,
    EmptyStatementError,
    MultipleStatementsError,
    SqlGuardError,
    UnauthorizedTableError,
)
from .guard import GuardResult, SqlGuard

__version__ = "0.1.0"

__all__ = [
    "DestructiveStatementError",
    "EmptyStatementError",
    "GuardResult",
    "MultipleStatementsError",
    "SqlGuard",
    "SqlGuardError",
    "UnauthorizedTableError",
]
