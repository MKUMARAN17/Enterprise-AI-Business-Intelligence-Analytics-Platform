"""Exception hierarchy for :mod:`bi_guardrails`.

Rejections here concern *user-supplied natural-language prompts* headed for an
LLM. As with the SQL guard, a rejection is an operational/security event, so the
base error subclasses :class:`RuntimeError`. :class:`UnsafePromptError` carries
the full :class:`~bi_guardrails.guard.ScanResult` so callers can log the matched
categories and surface a precise reason to the user without re-scanning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .guard import ScanResult


class GuardrailError(RuntimeError):
    """Base class for every guardrail rejection."""


class UnsafePromptError(GuardrailError):
    """Raised by :meth:`bi_guardrails.PromptGuard.enforce` for an unsafe prompt.

    The originating :class:`~bi_guardrails.guard.ScanResult` is attached as
    :attr:`result` so the caller has the matched categories, the reason, and the
    sanitized text available without running the scan again.
    """

    def __init__(self, result: ScanResult) -> None:
        self.result = result
        reason = result.reason or "prompt rejected by guardrails"
        super().__init__(reason)
