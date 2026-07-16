"""bi_guardrails — prompt-injection detection and input validation.

This package screens *user natural-language prompts* before they reach the LLM
in a natural-language-to-SQL BI platform. It flags prompt-injection / jailbreak
phrasing, embedded SQL/DDL, and shape problems (empty / over-length), returning
a structured :class:`ScanResult`.

Typical usage::

    from bi_guardrails import PromptGuard

    guard = PromptGuard(max_length=2000)
    result = guard.scan(user_text)
    if not result.safe:
        reject(result.reason)

    # or fail-closed:
    prompt = guard.enforce(user_text)   # raises UnsafePromptError if unsafe

A module-level :func:`scan_input` convenience is also provided.
"""

from __future__ import annotations

from .errors import GuardrailError, UnsafePromptError
from .guard import PromptGuard, ScanResult, scan_input

__version__ = "0.1.0"

__all__ = [
    "GuardrailError",
    "PromptGuard",
    "ScanResult",
    "UnsafePromptError",
    "scan_input",
]
