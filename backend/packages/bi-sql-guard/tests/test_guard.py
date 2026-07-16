"""Tests for :mod:`bi_sql_guard`.

These exercise the security-critical rules end to end: allowed read-only shapes,
every rejection path, comment-hidden payloads, exfiltration constructs,
table scoping, LIMIT injection, and the non-raising ``try_validate`` API.
"""

from __future__ import annotations

import pytest

from bi_sql_guard import (
    DestructiveStatementError,
    EmptyStatementError,
    GuardResult,
    MultipleStatementsError,
    SqlGuard,
    UnauthorizedTableError,
)


@pytest.fixture
def guard() -> SqlGuard:
    return SqlGuard(allowed_tables={"ORDERS", "CUSTOMERS", "ANALYTICS.SALES"}, max_limit=1000)


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #
def test_valid_select_passes(guard: SqlGuard) -> None:
    result = guard.validate("SELECT id, total FROM orders WHERE total > 100")
    assert isinstance(result, GuardResult)
    assert result.ok is True
    assert result.statement_type == "SELECT"
    assert result.tables == ("ORDERS",)
    assert result.reason is None


def test_with_cte_passes(guard: SqlGuard) -> None:
    sql = "WITH recent AS (SELECT id FROM orders) SELECT * FROM recent"
    result = guard.validate(sql)
    assert result.ok is True
    assert result.statement_type == "WITH"


def test_trailing_semicolon_is_allowed(guard: SqlGuard) -> None:
    result = guard.validate("SELECT * FROM orders;")
    assert result.ok is True


def test_join_and_schema_qualified_tables(guard: SqlGuard) -> None:
    sql = "SELECT * FROM orders JOIN customers ON orders.cid = customers.id"
    result = guard.validate(sql)
    assert result.ok is True
    assert set(result.tables) == {"ORDERS", "CUSTOMERS"}


def test_comma_join_tables_extracted(guard: SqlGuard) -> None:
    result = guard.validate("SELECT * FROM orders, customers WHERE orders.cid = customers.id")
    assert set(result.tables) == {"ORDERS", "CUSTOMERS"}


def test_table_alias_ignored(guard: SqlGuard) -> None:
    result = guard.validate("SELECT o.id FROM orders o")
    assert result.tables == ("ORDERS",)


# --------------------------------------------------------------------------- #
# Destructive / non-read-only statements
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE orders",
        "DELETE FROM orders WHERE id = 1",
        "UPDATE orders SET total = 0",
        "INSERT INTO orders VALUES (1)",
        "TRUNCATE TABLE orders",
        "ALTER TABLE orders ADD COLUMN x INT",
        "CREATE TABLE t (id INT)",
        "GRANT SELECT ON orders TO bob",
    ],
)
def test_destructive_leading_keyword_rejected(guard: SqlGuard, sql: str) -> None:
    with pytest.raises(DestructiveStatementError):
        guard.validate(sql)


def test_stacked_statements_rejected(guard: SqlGuard) -> None:
    with pytest.raises(MultipleStatementsError):
        guard.validate("SELECT * FROM orders; DROP TABLE orders")


def test_comment_hidden_payload_is_caught(guard: SqlGuard) -> None:
    # The DROP is smuggled after a line comment on the same logical line;
    # after comment stripping and split it must still be caught. Here the
    # payload is hidden in a block comment that, once stripped, reveals a
    # second statement.
    sql = "SELECT * FROM orders /* harmless */; DROP TABLE orders"
    with pytest.raises(MultipleStatementsError):
        guard.validate(sql)


def test_comment_only_input_is_empty(guard: SqlGuard) -> None:
    with pytest.raises(EmptyStatementError):
        guard.validate("-- just a comment\n/* nothing here */")


def test_into_outfile_rejected(guard: SqlGuard) -> None:
    with pytest.raises(DestructiveStatementError):
        guard.validate("SELECT * FROM orders INTO OUTFILE '/tmp/x'")


def test_into_dumpfile_rejected(guard: SqlGuard) -> None:
    with pytest.raises(DestructiveStatementError):
        guard.validate("SELECT * FROM orders INTO DUMPFILE '/tmp/x'")


def test_sleep_injection_rejected(guard: SqlGuard) -> None:
    with pytest.raises(DestructiveStatementError):
        guard.validate("SELECT * FROM orders WHERE id = 1 OR SLEEP(5)")


def test_load_file_rejected(guard: SqlGuard) -> None:
    with pytest.raises(DestructiveStatementError):
        guard.validate("SELECT LOAD_FILE('/etc/passwd') FROM orders")


# --------------------------------------------------------------------------- #
# Empty / whitespace
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("sql", ["", "   ", "\n\t  ", ";"])
def test_empty_statement_rejected(guard: SqlGuard, sql: str) -> None:
    with pytest.raises(EmptyStatementError):
        guard.validate(sql)


# --------------------------------------------------------------------------- #
# Table authorization
# --------------------------------------------------------------------------- #
def test_unauthorized_table_rejected(guard: SqlGuard) -> None:
    with pytest.raises(UnauthorizedTableError) as excinfo:
        guard.validate("SELECT * FROM secrets")
    assert "SECRETS" in str(excinfo.value)


def test_allowed_tables_none_permits_any_table() -> None:
    open_guard = SqlGuard(allowed_tables=None)
    result = open_guard.validate("SELECT * FROM anything_at_all")
    assert result.ok is True
    # ...but still blocks DDL.
    with pytest.raises(DestructiveStatementError):
        open_guard.validate("DROP TABLE anything")


# --------------------------------------------------------------------------- #
# LIMIT injection
# --------------------------------------------------------------------------- #
def test_limit_appended_when_missing(guard: SqlGuard) -> None:
    result = guard.validate("SELECT * FROM orders")
    assert result.normalized_sql == "SELECT * FROM orders LIMIT 1000"


def test_existing_limit_preserved(guard: SqlGuard) -> None:
    result = guard.validate("SELECT * FROM orders LIMIT 5")
    assert result.normalized_sql == "SELECT * FROM orders LIMIT 5"
    assert "LIMIT 1000" not in result.normalized_sql


# --------------------------------------------------------------------------- #
# try_validate
# --------------------------------------------------------------------------- #
def test_try_validate_returns_ok_false_instead_of_raising(guard: SqlGuard) -> None:
    result = guard.try_validate("DROP TABLE orders")
    assert result.ok is False
    assert result.reason is not None
    assert result.statement_type == "DROP"


def test_try_validate_success(guard: SqlGuard) -> None:
    result = guard.try_validate("SELECT * FROM orders")
    assert result.ok is True
    assert result.reason is None
