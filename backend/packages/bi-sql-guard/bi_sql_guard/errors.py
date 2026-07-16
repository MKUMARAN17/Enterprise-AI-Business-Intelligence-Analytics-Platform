"""Exception hierarchy for :mod:`bi_sql_guard`.

The guard is a *security boundary*: it decides whether LLM-generated SQL is
allowed to reach the database. Every rejection therefore raises a specific,
typed exception rather than returning a soft error code. Callers that treat any
:class:`SqlGuardError` as "deny" get fail-closed behaviour for free, while
callers that need to explain *why* a query was rejected can branch on the
concrete subclass.

All errors subclass :class:`SqlGuardError`, which in turn subclasses
:class:`RuntimeError` (not :class:`ValueError`) because a rejected statement is
an operational/security event, not merely a bad function argument.
"""

from __future__ import annotations


class SqlGuardError(RuntimeError):
    """Base class for every rejection raised by :class:`bi_sql_guard.SqlGuard`.

    Catch this to implement a blanket fail-closed policy: if the guard raised
    anything, do not run the SQL.
    """


class EmptyStatementError(SqlGuardError):
    """Raised when the SQL is empty or whitespace/comment-only after cleaning."""


class MultipleStatementsError(SqlGuardError):
    """Raised when more than one statement is submitted in a single string.

    Stacked statements (``SELECT ...; DROP TABLE users``) are a classic
    injection vector, so the guard permits exactly one statement (an optional
    single trailing ``;`` is tolerated).
    """


class DestructiveStatementError(SqlGuardError):
    """Raised for anything that can mutate or exfiltrate data.

    This covers DDL/DML leading keywords (INSERT, UPDATE, DROP, ...) as well as
    dangerous constructs anywhere in the token stream (``INTO OUTFILE``,
    ``LOAD_FILE``, ``SLEEP(`` etc.).
    """


class UnauthorizedTableError(SqlGuardError):
    """Raised when a query references a table outside the caller's allow-list.

    The offending table names are included in the message so the platform can
    surface an actionable, role-aware error to the user.
    """
