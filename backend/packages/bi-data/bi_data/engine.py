"""Read-only query execution against the ENTERPRISE_BI database.

Defence in depth: the SQL guard has already proven the statement is a single
SELECT touching only permitted tables, but this layer adds a second, independent
safety net at the point of execution:

  * queries run inside a transaction that is ALWAYS rolled back (never
    committed), so even a hypothetical write that slipped the guard leaves no
    trace;
  * a hard row cap (`fetchmany`) bounds memory regardless of any LIMIT;
  * results are materialised into an immutable :class:`Dataset` — the caller
    never gets a live cursor or an ORM session to misuse.

The engine is created once at boot from a SQLAlchemy URL. ``pool_pre_ping`` keeps
long-lived connections healthy behind the connection pool.
"""
from __future__ import annotations

from bi_base.errors import ConfigError, QueryExecutionError
from bi_base.logging import get_logger
from bi_base.timing import stopwatch
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from bi_data.dataset import Dataset

log = get_logger(__name__)


class QueryRunner:
    """Executes validated SELECTs and returns Datasets. Read-only by construction."""

    def __init__(self, engine: Engine, *, default_max_rows: int = 10000):
        self._engine = engine
        self._default_max_rows = default_max_rows

    @classmethod
    def from_url(cls, url: str, *, echo: bool = False, default_max_rows: int = 10000) -> QueryRunner:
        if not url:
            raise ConfigError("database URL is required to build the QueryRunner")
        engine = create_engine(url, pool_pre_ping=True, echo=echo, future=True)
        return cls(engine, default_max_rows=default_max_rows)

    @property
    def engine(self) -> Engine:
        return self._engine

    def execute(
        self,
        sql: str,
        *,
        params: dict | None = None,
        max_rows: int | None = None,
    ) -> Dataset:
        """Run a (already guard-validated) SELECT and return a Dataset.

        Raises :class:`QueryExecutionError` on any driver/SQL failure — the raw
        driver message is logged but not surfaced to the API caller.
        """
        cap = max_rows or self._default_max_rows
        try:
            with stopwatch() as elapsed, self._engine.connect() as conn:  # noqa: SIM117 - timer must wrap the connection
                # begin() + rollback on exit → nothing is ever committed.
                with conn.begin() as txn:
                    result = conn.execute(text(sql), params or {})
                    # .keys() is SQLAlchemy's Result key view, not a dict — iterating
                    # the Result directly would yield rows, not column names.
                    columns = tuple(str(c).upper() for c in result.keys())  # noqa: SIM118
                    fetched = result.fetchmany(cap)
                    rows = tuple(tuple(row) for row in fetched)
                    txn.rollback()
            log.info("sql.executed", rows=len(rows), ms=elapsed.ms, columns=len(columns))
            return Dataset(columns=columns, rows=rows)
        except SQLAlchemyError as exc:
            log.warning("sql.failed", error=str(exc)[:300])
            raise QueryExecutionError("query execution failed") from exc

    def dispose(self) -> None:
        self._engine.dispose()
