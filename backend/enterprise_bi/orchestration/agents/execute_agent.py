"""Query execution node.

Runs the validated SQL via the read-only :class:`bi_data.QueryRunner` and lands
the result (columns + rows + timing) on the state. Not an LLM step — deterministic
and bounded. A driver failure is caught and turned into an ERROR state so the
graph still reaches the response node with a clean problem-details body.
"""
from __future__ import annotations

from bi_base.errors import QueryExecutionError
from bi_base.logging import get_logger

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_execute_node(deps: GraphDeps):
    def execute_node(state: BIState) -> dict:
        sql = state.get("validated_sql") or state.get("sql", "")
        try:
            ds = deps.query_runner.execute(sql, max_rows=deps.max_rows)
        except QueryExecutionError as exc:
            log.warning("agent.execute_failed", error=str(exc))
            return {
                "status": "ERROR",
                "error": {"code": exc.code, "message": exc.message},
            }
        return {
            "columns": list(ds.columns),
            "rows": [list(r) for r in ds.rows],
            "row_count": ds.row_count,
        }

    return execute_node
