"""Agent 2 — Schema Retrieval Agent (RAG).

Retrieves only the relevant slice of the database schema + business glossary for
this question, so the SQL agent is grounded in real table/column names (never
hallucinated ones) without being handed the entire schema. The retrieved tables
are intersected with the caller's RBAC allow-list up front, so the SQL agent is
only ever shown tables the user is permitted to read.
"""
from __future__ import annotations

from bi_base.logging import get_logger

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_schema_node(deps: GraphDeps):
    def schema_node(state: BIState) -> dict:
        allowed = {t.upper() for t in state.get("allowed_tables", [])}
        chunks = deps.retriever.retrieve(state["question"], k=8)
        # Keep table chunks the caller may read; always keep glossary chunks.
        kept = [
            c
            for c in chunks
            if c.kind != "table" or (not allowed or c.name.upper() in allowed)
        ]
        context = deps.retriever.format_context(kept)
        retrieved_tables = [c.name.upper() for c in kept if c.kind == "table"]
        log.info("agent.schema", retrieved=len(retrieved_tables))
        return {"schema_context": context, "retrieved_tables": retrieved_tables}

    return schema_node
