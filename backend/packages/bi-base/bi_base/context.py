"""Per-request correlation context.

A single ``request_id`` is minted at the HTTP boundary and stashed in a
``ContextVar`` so every log line emitted anywhere down the call stack (agents,
SQL guard, data layer) is automatically tagged with it — without threading the
id through every function signature. This is what makes the AUDIT_LOG row and
the structured logs for one turn joinable after the fact.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("bi_request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("bi_user_id", default=None)


def new_request_id() -> str:
    """Generate a fresh, URL-safe correlation id."""
    return uuid.uuid4().hex


def bind_request(request_id: str | None = None, user_id: str | None = None) -> str:
    """Bind the request context for the current async task; returns the id in use."""
    rid = request_id or new_request_id()
    _request_id.set(rid)
    if user_id is not None:
        _user_id.set(user_id)
    return rid


def get_request_id() -> str | None:
    return _request_id.get()


def get_user_id() -> str | None:
    return _user_id.get()


def clear() -> None:
    _request_id.set(None)
    _user_id.set(None)
