"""The shared error hierarchy + a stable problem-details shape.

Every layer of the platform raises subclasses of :class:`BiError`, and the HTTP
boundary renders any :class:`BiError` into RFC-7807-style problem details via
:meth:`BiError.to_problem`. Keeping one root error with a machine-readable
``code`` lets the API return consistent, non-leaky error bodies (we never surface
raw SQL/driver text to the caller) while the ``status_code`` drives the HTTP
response. Layers below the API import only what they need and never depend on
FastAPI.
"""
from __future__ import annotations

from dataclasses import dataclass


class BiError(RuntimeError):
    """Base for every platform error.

    ``code`` is a stable, screaming-snake identifier the frontend can branch on;
    ``status_code`` is the HTTP status the API boundary should emit. Subclasses
    set sensible defaults so call sites can ``raise SqlSafetyError("...")``.
    """

    code: str = "BI_ERROR"
    status_code: int = 500

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code

    def to_problem(self) -> dict[str, object]:
        """Render an RFC-7807-ish problem-details body (safe to send to clients)."""
        return {"code": self.code, "message": self.message, "status": self.status_code}


class ConfigError(BiError):
    """Missing/invalid configuration discovered at boot — fail closed."""

    code = "CONFIG_ERROR"
    status_code = 500


class AuthError(BiError):
    """Authentication failed (bad/expired/absent token)."""

    code = "AUTH_ERROR"
    status_code = 401


class AuthorizationError(BiError):
    """The caller is authenticated but not permitted (RBAC denial)."""

    code = "FORBIDDEN"
    status_code = 403


class GuardrailError(BiError):
    """Input rejected by prompt guardrails."""

    code = "GUARDRAIL_BLOCKED"
    status_code = 400


class SqlSafetyError(BiError):
    """Generated SQL failed the safety guard."""

    code = "SQL_UNSAFE"
    status_code = 400


class QueryExecutionError(BiError):
    """The database rejected or failed to run a validated query."""

    code = "QUERY_FAILED"
    status_code = 422


class AgentError(BiError):
    """An orchestration agent could not complete its step."""

    code = "AGENT_ERROR"
    status_code = 502


@dataclass(frozen=True, slots=True)
class ProblemDetail:
    """Typed mirror of :meth:`BiError.to_problem` for callers that prefer a value."""

    code: str
    message: str
    status: int
