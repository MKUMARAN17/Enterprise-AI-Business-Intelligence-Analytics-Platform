"""Agent 3 — SQL Generation Agent.

Turns the natural-language question + retrieved schema context into a single
MySQL SELECT. The prompt instructs the model to use only UPPERCASE identifiers
(matching the physical schema), to aggregate/join/filter as needed, and to return
a JSON plan (``sql`` + ``tables`` + ``rationale``) rather than bare SQL — the
structured shape lets the validator cross-check the declared tables against what
the guard actually parses.
"""
from __future__ import annotations

from bi_base.logging import get_logger

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_sql_node(deps: GraphDeps):
    def sql_node(state: BIState) -> dict:
        intent = state.get("intent", {})
        result = deps.router.run(
            "sql_plan",
            question=state["question"],
            schema=state.get("schema_context", ""),
            domain=intent.get("domain", ""),
            allowed_tables=", ".join(state.get("allowed_tables", [])),
        )
        sql = str(result.get("sql", "")).strip()
        log.info("agent.sql_generated", tables=result.get("tables"))
        return {
            "sql": sql,
            "sql_tables": [str(t).upper() for t in result.get("tables", [])],
            "sql_rationale": str(result.get("rationale", "")),
        }

    return sql_node
