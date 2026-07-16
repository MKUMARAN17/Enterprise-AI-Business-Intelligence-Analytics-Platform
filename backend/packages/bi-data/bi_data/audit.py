"""AUDIT_LOG writer.

Functional requirement: "Every request stores User, Prompt, SQL, Execution Time,
Charts Generated, Reports Downloaded." This writer persists one AUDIT_LOG row per
turn on its OWN short-lived connection (committed — unlike analytical queries),
so the audit trail survives even when the analytical query itself was blocked or
errored. It never raises into the request path: an audit failure is logged, not
propagated, so logging can't take down the feature it audits.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from bi_base.logging import get_logger
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

log = get_logger(__name__)

_INSERT = text(
    """
    INSERT INTO AUDIT_LOG
        (USER_ID, USERNAME, ROLE_NAME, REQUEST_ID, PROMPT, GENERATED_SQL, INTENT,
         EXECUTION_MS, ROW_COUNT, CHART_KIND, REPORT_FORMAT, STATUS, ERROR_MESSAGE)
    VALUES
        (:user_id, :username, :role_name, :request_id, :prompt, :generated_sql, :intent,
         :execution_ms, :row_count, :chart_kind, :report_format, :status, :error_message)
    """
)


@dataclass(frozen=True, slots=True)
class AuditEntry:
    request_id: str
    prompt: str
    user_id: str | None = None
    username: str | None = None
    role_name: str | None = None
    generated_sql: str | None = None
    intent: str | None = None
    execution_ms: int | None = None
    row_count: int | None = None
    chart_kind: str | None = None
    report_format: str | None = None
    status: str = "OK"
    error_message: str | None = None


class AuditLogWriter:
    def __init__(self, engine: Engine):
        self._engine = engine

    def write(self, entry: AuditEntry) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(_INSERT, asdict(entry))
        except SQLAlchemyError as exc:  # never break the request because audit failed
            log.warning("audit.write_failed", error=str(exc)[:200], request_id=entry.request_id)
