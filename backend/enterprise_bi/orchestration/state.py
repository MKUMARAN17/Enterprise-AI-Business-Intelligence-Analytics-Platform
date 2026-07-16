"""The turn state carried through the LangGraph.

One ``BIState`` dict flows node-to-node (intent → schema → SQL → validate →
execute → analytics → viz → insight → respond). LangGraph merges each node's
returned partial dict into the running state, so nodes only return the keys they
change. Keys are grouped by the stage that produces them; ``error`` short-circuits
the graph to the terminal response node.
"""
from __future__ import annotations

from typing import Any, TypedDict


class BIState(TypedDict, total=False):
    # ── inputs ────────────────────────────────────────────────────────────
    request_id: str
    question: str
    user_id: str
    username: str
    role: str
    allowed_tables: list[str]
    history: list[dict[str, str]]  # follow-up conversation memory

    # ── intent stage ──────────────────────────────────────────────────────
    intent: dict[str, Any]

    # ── schema-RAG stage ──────────────────────────────────────────────────
    schema_context: str
    retrieved_tables: list[str]

    # ── SQL stage ─────────────────────────────────────────────────────────
    sql: str
    sql_tables: list[str]
    sql_rationale: str
    validated_sql: str

    # ── execution stage ───────────────────────────────────────────────────
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    execution_ms: float

    # ── analytics / viz / insight ─────────────────────────────────────────
    analytics: dict[str, Any]
    visualization: dict[str, Any]
    insight: dict[str, Any]

    # ── control / output ──────────────────────────────────────────────────
    export_format: str | None
    chart_kind: str | None
    error: dict[str, Any] | None
    status: str  # OK | BLOCKED | ERROR
