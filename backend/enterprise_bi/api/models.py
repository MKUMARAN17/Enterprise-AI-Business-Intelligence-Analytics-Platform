"""Request/response schemas for the conversation API (the HTTP contract)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    question: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    history: list[HistoryTurn] = Field(default_factory=list)


class AskResponse(BaseModel):
    request_id: str | None = None
    status: str
    intent: dict[str, Any] | None = None
    generated_sql: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    analytics: dict[str, Any] = Field(default_factory=dict)
    visualization: dict[str, Any] = Field(default_factory=dict)
    insight: dict[str, Any] = Field(default_factory=dict)
    export: dict[str, Any] | None = None
    execution_ms: float | None = None
    error: dict[str, Any] | None = None
