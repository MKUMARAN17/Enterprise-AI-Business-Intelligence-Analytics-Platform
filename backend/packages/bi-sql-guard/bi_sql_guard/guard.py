"""Static validation of LLM-generated SQL before it touches the database.

This module implements the load-bearing security check for a
natural-language-to-SQL platform. An LLM turns a user's question into SQL; that
SQL is *untrusted* and must be treated as hostile until proven read-only and
scoped to the tables the current role may see.

Design principles
-----------------
* **Fail closed.** :meth:`SqlGuard.validate` *raises* on any violation. There is
  no "warn and continue" path. A convenience :meth:`SqlGuard.try_validate`
  returns a :class:`GuardResult` with ``ok=False`` for callers that prefer a
  result object over exception handling.
* **Defence in depth.** We check the leading keyword (rule 4) *and* scan the
  whole token stream for dangerous constructs (rule 5), so a payload smuggled
  past one rule is still caught by another.
* **No external parser.** We deliberately avoid a full SQL grammar/parser
  dependency: this stays pure-stdlib and auditable. The trade-off is that table
  extraction is heuristic (regex-based). See :meth:`SqlGuard._extract_tables`
  for the documented limitations. Because the guard only *allows* SELECT and
  scopes tables against an allow-list, an imperfect extraction fails closed
  (an unrecognised table simply is not in the allow-list).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import (
    DestructiveStatementError,
    EmptyStatementError,
    MultipleStatementsError,
    SqlGuardError,
    UnauthorizedTableError,
)

# --------------------------------------------------------------------------- #
# Keyword and pattern tables
# --------------------------------------------------------------------------- #

# Leading keywords that indicate a statement is not a read-only query. If a
# statement *starts* with any of these it is rejected outright (rule 4).
_DESTRUCTIVE_LEADING_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "REPLACE",
        "MERGE",
        "CALL",
        "EXEC",
        "EXECUTE",
        "SET",
        "USE",
        "LOCK",
        "UNLOCK",
        "RENAME",
    }
)

# Standalone keywords that must never appear anywhere in a read-only query.
# These catch mutations/DDL hidden after a legal-looking prefix (defence in
# depth on top of the single-statement rule).
_DESTRUCTIVE_TOKENS: frozenset[str] = frozenset(
    _DESTRUCTIVE_LEADING_KEYWORDS
    | {
        "OUTFILE",
        "DUMPFILE",
    }
)

# Dangerous multi-word / function constructs used for exfiltration or
# denial-of-service. Matched as regexes over the cleaned SQL. Each entry maps a
# compiled pattern to a human-readable reason.
_DANGEROUS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bINTO\s+OUTFILE\b", re.IGNORECASE), "INTO OUTFILE (file exfiltration)"),
    (re.compile(r"\bINTO\s+DUMPFILE\b", re.IGNORECASE), "INTO DUMPFILE (file exfiltration)"),
    (re.compile(r"\bLOAD_FILE\s*\(", re.IGNORECASE), "LOAD_FILE( (file read)"),
    (re.compile(r"\bSLEEP\s*\(", re.IGNORECASE), "SLEEP( (time-based injection / DoS)"),
    (re.compile(r"\bBENCHMARK\s*\(", re.IGNORECASE), "BENCHMARK( (DoS)"),
)

# Comment strippers. Block comments are non-greedy and span newlines; line
# comments run to end-of-line. Stripped BEFORE analysis so a payload cannot
# hide inside a comment.
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")

# A word token: a SQL identifier fragment. Used to find the leading keyword and
# to scan for standalone destructive tokens.
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Table references after FROM / JOIN. We capture the first identifier (with an
# optional ``db.`` qualifier) following the keyword. A following alias, ``ON``
# clause, comma, or parenthesis simply terminates the match.
_TABLE_SOURCE_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+(?P<ref>[A-Za-z_][\w.]*)",
    re.IGNORECASE,
)

# LIMIT presence check (word-boundary so it does not match e.g. ``LIMITED``).
_LIMIT_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)

# Names introduced by a WITH clause (CTEs) or a derived-table alias: an
# identifier immediately followed by ``AS (``. These are *not* base tables and
# must be excluded from allow-list authorization (a real table reference is
# never written ``orders AS (`` — an alias there is always parenthesised SQL).
_CTE_NAME_RE = re.compile(r"\b([A-Za-z_]\w*)\s+AS\s*\(", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class GuardResult:
    """Outcome of validating a single SQL statement.

    Attributes
    ----------
    ok:
        ``True`` if the statement passed every rule.
    statement_type:
        The leading keyword, uppercased (e.g. ``"SELECT"``, ``"WITH"``). Best
        effort even on failure so callers can log what was attempted.
    tables:
        Uppercased table names referenced by the query, in first-seen order and
        de-duplicated. Empty when extraction found none (or on early failures).
    reason:
        Human-readable rejection reason, or ``None`` when ``ok`` is ``True``.
    normalized_sql:
        The cleaned SQL (comments stripped, trailing ``;`` removed) with a
        safety ``LIMIT`` appended when the query lacked one. On failure this is
        the cleaned input as far as it could be processed.
    """

    ok: bool
    statement_type: str
    tables: tuple[str, ...]
    reason: str | None
    normalized_sql: str


class SqlGuard:
    """Validate that a SQL string is a safe, read-only, in-scope query.

    Parameters
    ----------
    allowed_tables:
        Set of UPPERCASE table names the current role may read. When ``None``
        (the default) any table name is accepted *for authorization purposes*,
        but DDL/DML and dangerous constructs are still blocked. Pass an explicit
        set to enforce row-source scoping per role.
    max_limit:
        The safety ``LIMIT`` appended to queries that lack one, and thus the
        maximum number of rows a guarded query can return by default.

    The guard is stateless and therefore safe to share across threads/requests.
    """

    def __init__(
        self,
        allowed_tables: set[str] | None = None,
        max_limit: int = 10000,
    ) -> None:
        # Normalise the allow-list to uppercase once so lookups are trivial and
        # case-insensitive. ``None`` is preserved to mean "no table scoping".
        self._allowed_tables: frozenset[str] | None = (
            frozenset(t.upper() for t in allowed_tables) if allowed_tables is not None else None
        )
        if max_limit <= 0:
            raise ValueError("max_limit must be a positive integer")
        self._max_limit = max_limit

    # ----------------------------------------------------------------- #
    # Public API
    # ----------------------------------------------------------------- #
    def validate(self, sql: str) -> GuardResult:
        """Validate ``sql`` and return a passing :class:`GuardResult`.

        Raises a specific :class:`~bi_sql_guard.errors.SqlGuardError` subclass on
        the first rule violation (fail-closed). This is the method to call from
        the query execution path: if it returns, the SQL is safe to run.

        Prefer :meth:`try_validate` if you want a result object instead of
        exception handling.
        """
        cleaned = self._strip_comments(sql)

        statements = self._split_statements(cleaned)
        if not statements:
            raise EmptyStatementError("SQL is empty after removing comments and whitespace")
        if len(statements) > 1:
            raise MultipleStatementsError(
                f"expected a single statement, found {len(statements)} "
                "(stacked statements are not allowed)"
            )

        statement = statements[0]
        statement_type = self._leading_keyword(statement)

        # Rule 4: only SELECT / WITH...SELECT are permitted.
        if statement_type in _DESTRUCTIVE_LEADING_KEYWORDS:
            raise DestructiveStatementError(
                f"statement type {statement_type!r} is not permitted; only read-only "
                "SELECT / WITH queries are allowed"
            )
        if statement_type not in {"SELECT", "WITH"}:
            raise DestructiveStatementError(
                f"unrecognised or non-read-only statement type {statement_type or '<empty>'!r}; "
                "only SELECT / WITH queries are allowed"
            )

        # Rule 5: scan the whole statement for dangerous constructs.
        self._scan_dangerous(statement)

        # Rule 6: extract and authorize referenced tables.
        tables = self._extract_tables(statement)
        if self._allowed_tables is not None:
            unauthorized = tuple(t for t in tables if t not in self._allowed_tables)
            if unauthorized:
                raise UnauthorizedTableError(
                    "query references table(s) not permitted for this role: "
                    + ", ".join(unauthorized)
                )

        # Rule 7: append a safety LIMIT when absent.
        normalized = self._apply_limit(statement)

        return GuardResult(
            ok=True,
            statement_type=statement_type,
            tables=tables,
            reason=None,
            normalized_sql=normalized,
        )

    def try_validate(self, sql: str) -> GuardResult:
        """Non-raising variant of :meth:`validate`.

        Returns a passing :class:`GuardResult` on success, or a
        ``GuardResult(ok=False, reason=...)`` describing the first violation.
        Useful in batch/preview contexts where you want to collect results
        rather than handle exceptions. The execution path should still prefer
        :meth:`validate` for its explicit fail-closed contract.
        """
        try:
            return self.validate(sql)
        except SqlGuardError as exc:
            cleaned = self._strip_comments(sql)
            statements = self._split_statements(cleaned)
            statement = statements[0] if statements else cleaned.strip()
            return GuardResult(
                ok=False,
                statement_type=self._leading_keyword(statement),
                tables=(),
                reason=str(exc),
                normalized_sql=statement,
            )

    # ----------------------------------------------------------------- #
    # Internal helpers
    # ----------------------------------------------------------------- #
    @staticmethod
    def _strip_comments(sql: str) -> str:
        """Remove block and line comments (rule 1).

        Comments are stripped *before* any analysis so an attacker cannot hide a
        payload behind ``--`` or inside ``/* ... */``. Block comments are
        replaced with a space to avoid accidentally gluing two tokens together
        (e.g. ``a/**/b`` must not become the single token ``ab``).
        """
        without_block = _BLOCK_COMMENT_RE.sub(" ", sql)
        without_line = _LINE_COMMENT_RE.sub("", without_block)
        return without_line

    @staticmethod
    def _split_statements(cleaned_sql: str) -> list[str]:
        """Split on ``;`` and return non-empty, stripped statements (rule 3).

        A single trailing ``;`` yields exactly one statement. This is a simple
        split; because we ultimately only allow SELECT/WITH and reject dangerous
        constructs, a ``;`` appearing inside a string literal would at worst
        cause a legitimate query to be flagged as multiple statements, which is
        an acceptable fail-closed outcome for a BI read path.
        """
        return [part.strip() for part in cleaned_sql.split(";") if part.strip()]

    @staticmethod
    def _leading_keyword(statement: str) -> str:
        """Return the first word token of ``statement``, uppercased.

        Returns an empty string when the statement has no word tokens.
        """
        match = _WORD_RE.search(statement)
        return match.group(0).upper() if match else ""

    @staticmethod
    def _scan_dangerous(statement: str) -> None:
        """Raise if any destructive token or dangerous construct is present.

        Implements rule 5's defence-in-depth scan. Two complementary checks:

        * every word token is compared against :data:`_DESTRUCTIVE_TOKENS`, so a
          bare ``DROP``/``DELETE``/``OUTFILE`` anywhere is caught even if the
          statement began with ``SELECT``;
        * multi-word / function constructs (``INTO OUTFILE``, ``SLEEP(`` ...)
          are matched with the regexes in :data:`_DANGEROUS_PATTERNS`.
        """
        for token in _WORD_RE.findall(statement):
            upper = token.upper()
            if upper in _DESTRUCTIVE_TOKENS:
                raise DestructiveStatementError(
                    f"destructive keyword {upper!r} found in query body"
                )
        for pattern, reason in _DANGEROUS_PATTERNS:
            if pattern.search(statement):
                raise DestructiveStatementError(f"dangerous construct detected: {reason}")

    @staticmethod
    def _extract_tables(statement: str) -> tuple[str, ...]:
        """Heuristically extract referenced table names, uppercased (rule 6).

        Handles the common shapes produced by text-to-SQL models:

        * ``FROM tbl`` and ``FROM tbl alias``
        * ``FROM db.tbl`` (schema-qualified; kept as ``DB.TBL``)
        * ``JOIN tbl ON ...``
        * comma joins ``FROM a, b`` (the ``b`` is picked up because the split
          below re-scans comma-separated sources)

        Names introduced by a ``WITH`` clause (CTEs) or derived-table aliases
        (``... AS (SELECT ...)``) are recognised and excluded, since referencing
        them in a later ``FROM`` is not a base-table access and must not be
        authorized against the allow-list.

        Limitations (documented deliberately): derived tables / subqueries in
        the FROM clause and table-valued functions are not resolved to base
        tables, and quoted identifiers with embedded punctuation are not fully
        supported. Because authorization is an allow-list check, any name we
        fail to recognise cannot slip past scoping — it simply will not match an
        allowed table, i.e. the heuristic fails closed.
        """
        # Names defined by CTEs / derived tables are local aliases, not tables.
        cte_names = {name.upper() for name in _CTE_NAME_RE.findall(statement)}

        found: list[str] = []
        seen: set[str] = set(cte_names)

        # First, capture the source immediately after each FROM/JOIN.
        for match in _TABLE_SOURCE_RE.finditer(statement):
            ref = match.group("ref").upper()
            # Handle a comma-join tail on the same clause, e.g. "FROM a, b, c".
            # Re-scan the region after the keyword for further comma sources.
            _add_unique(ref, found, seen)

        # Comma joins: after a FROM ... clause, additional tables appear as
        # ``, tbl``. Capture identifiers that immediately follow a comma and are
        # not preceded by a function/column context. This is intentionally
        # scoped to the FROM segment to avoid catching SELECT-list columns.
        from_segment = _from_segment(statement)
        if from_segment:
            for ref in re.findall(r",\s*([A-Za-z_][\w.]*)", from_segment):
                _add_unique(ref.upper(), found, seen)

        return tuple(found)

    def _apply_limit(self, statement: str) -> str:
        """Append ``LIMIT max_limit`` when the query has none (rule 7).

        Guards against an LLM emitting an unbounded scan. If a ``LIMIT`` is
        already present we leave it untouched (we never *lower* an explicit
        limit here; that is a policy decision left to the caller).
        """
        if _LIMIT_RE.search(statement):
            return statement
        return f"{statement} LIMIT {self._max_limit}"


def _add_unique(ref: str, found: list[str], seen: set[str]) -> None:
    """Append ``ref`` to ``found`` preserving first-seen order, de-duplicated."""
    if ref and ref not in seen:
        seen.add(ref)
        found.append(ref)


def _from_segment(statement: str) -> str:
    """Return the FROM...(pre-WHERE/GROUP/ORDER/LIMIT) segment for comma scans.

    Isolating the FROM clause keeps comma-join detection from misfiring on
    commas in the SELECT list or elsewhere.
    """
    lowered = statement.lower()
    start = lowered.find("from")
    if start == -1:
        return ""
    # Terminate the segment at the first clause keyword that ends FROM.
    end = len(statement)
    for kw in (" where ", " group by ", " order by ", " having ", " limit ", " join "):
        idx = lowered.find(kw, start)
        if idx != -1:
            end = min(end, idx)
    return statement[start:end]
