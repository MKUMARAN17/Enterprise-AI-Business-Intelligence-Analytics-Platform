"""Agent 4 — SQL Validation Agent (the security gate).

The single most important node: no SQL reaches the database until it passes here.
It runs the generated SQL through :class:`bi_sql_guard.SqlGuard` scoped to the
caller's RBAC allow-list, which:
  * blocks anything that is not a single SELECT (DDL/DML/stacked statements),
  * rejects references to tables the role may not read,
  * appends a safety LIMIT.
On any violation it sets ``state['error']`` and marks the turn BLOCKED — the
conditional edge then routes straight to the response node, skipping execution.
"""
from __future__ import annotations

from bi_base.logging import get_logger
from bi_sql_guard import SqlGuardError

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_validate_node(deps: GraphDeps):
    def validate_node(state: BIState) -> dict:
        allowed = {t.upper() for t in state.get("allowed_tables", [])}
        guard = deps.sql_guard_factory(allowed_tables=allowed or None, max_limit=deps.max_rows)
        sql = state.get("sql", "")
        try:
            result = guard.validate(sql)
        except SqlGuardError as exc:
            log.warning("agent.sql_blocked", reason=str(exc))
            return {
                "status": "BLOCKED",
                "error": {"code": "SQL_UNSAFE", "message": str(exc)},
            }
        log.info("agent.sql_validated", tables=list(result.tables))
        return {"validated_sql": result.normalized_sql, "status": "OK"}

    return validate_node
