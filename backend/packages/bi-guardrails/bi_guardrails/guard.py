"""Prompt-injection detection and input validation for user NL prompts.

This runs *before* a user's natural-language question reaches the LLM. The goal
is to catch three classes of problem cheaply and deterministically:

* **Prompt injection / jailbreak** — attempts to override the system prompt,
  change the assistant's role, or extract its instructions.
* **Embedded SQL/DDL** — a NL prompt should describe *what* the user wants, not
  contain raw destructive SQL; such content is a strong signal of an attempt to
  smuggle commands through the text-to-SQL layer.
* **Shape problems** — empty prompts and prompts over the configured length
  budget (which also bounds token cost and blast radius).

Design notes
------------
* Detection is **regex-based and case-insensitive**, grouped into documented
  pattern families. This is intentionally a fast, explainable first line of
  defence — not a replacement for model-side safety. It favours recall on
  well-known attack phrasings; obfuscated/novel attacks are out of scope.
* :meth:`PromptGuard.scan` never raises for *content*; it returns a
  :class:`ScanResult` describing every matched category. Use
  :meth:`PromptGuard.enforce` when you want fail-closed behaviour (raise on
  anything unsafe).
* ``safe`` is simply ``len(categories) == 0`` — any single match makes the
  prompt unsafe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Detection pattern families
# --------------------------------------------------------------------------- #
# Each family maps a category label to the regexes that trigger it. Keeping the
# families explicit (rather than one mega-regex) makes the categories reported
# in ScanResult meaningful and the rules auditable.

_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "ignore previous/above instructions", "disregard all prior instructions"
    re.compile(
        r"\b(?:ignore|disregard|forget|override)\b[^.]{0,40}?"
        r"\b(?:previous|above|prior|earlier|all|any|the)\b[^.]{0,20}?"
        r"\b(?:instruction|instructions|prompt|prompts|context|rules?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\breveal\b[^.]{0,40}?\b(?:instruction|instructions|prompt|system prompt)\b", re.IGNORECASE),
    re.compile(r"\b(?:show|print|repeat|output)\b[^.]{0,30}?\b(?:system prompt|your instructions|your prompt)\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bbypass\b[^.]{0,30}?\b(?:filter|guardrail|guardrails|restriction|restrictions|safety|rules?)\b", re.IGNORECASE),
)

_JAILBREAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\b", re.IGNORECASE),
    re.compile(r"\bpretend\s+(?:to\s+be|you\s+are)\b", re.IGNORECASE),
    re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),  # "DAN"
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    # Role-hijack / chat-template markers.
    re.compile(r"#{2,}\s*system\b", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"\b(?:system|assistant|user)\s*:\s*$", re.IGNORECASE | re.MULTILINE),
)

# Embedded SQL/DDL inside what should be a natural-language prompt. Matched as
# standalone keywords so ordinary prose ("update me on sales") does not trip the
# DML words — we require a plausible SQL context (keyword followed by an object)
# or the classic ``;--`` comment-injection marker.
_SQL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA|VIEW|INDEX)\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bALTER\s+(?:TABLE|DATABASE|SCHEMA|VIEW)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+(?:TABLE\b)?", re.IGNORECASE),
    re.compile(r";\s*--", re.IGNORECASE),  # stacked-statement / comment injection
)

# Category label constants (also the public vocabulary of ScanResult.categories).
_CAT_PROMPT_INJECTION = "prompt_injection"
_CAT_JAILBREAK = "jailbreak"
_CAT_SQL_INJECTION = "sql_injection"
_CAT_TOO_LONG = "too_long"
_CAT_EMPTY = "empty"

# Collapses any run of whitespace (including newlines/tabs) to a single space.
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Outcome of scanning a single natural-language prompt.

    Attributes
    ----------
    safe:
        ``True`` when no category matched (``len(categories) == 0``).
    categories:
        The matched category labels, de-duplicated and in a stable order:
        ``"prompt_injection"``, ``"jailbreak"``, ``"sql_injection"``,
        ``"too_long"``, ``"empty"``.
    reason:
        Human-readable summary of why the prompt is unsafe, or ``None`` when
        ``safe`` is ``True``.
    sanitized:
        The input with surrounding whitespace trimmed and internal runs of
        whitespace collapsed to single spaces. This is the text callers should
        forward to the LLM when the prompt is safe.
    """

    safe: bool
    categories: tuple[str, ...]
    reason: str | None
    sanitized: str


class PromptGuard:
    """Scan user prompts for injection/jailbreak/SQL content and shape problems.

    Parameters
    ----------
    max_length:
        Maximum allowed length (in characters) of the *sanitized* prompt. Longer
        prompts are flagged ``too_long``. This bounds token cost and limits the
        room an attacker has to hide instructions.

    The guard is stateless and safe to reuse across threads/requests.
    """

    def __init__(self, max_length: int = 2000) -> None:
        if max_length <= 0:
            raise ValueError("max_length must be a positive integer")
        self._max_length = max_length

    def scan(self, text: str) -> ScanResult:
        """Scan ``text`` and return a :class:`ScanResult` (never raises).

        The prompt is first sanitized (trimmed + whitespace-collapsed); detection
        runs against the sanitized text so that padding tricks (excess spacing /
        newlines) cannot split an attack phrase across whitespace.
        """
        sanitized = self._sanitize(text)
        categories: list[str] = []

        if not sanitized:
            # Empty is a terminal shape problem — no point running content rules.
            return ScanResult(
                safe=False,
                categories=(_CAT_EMPTY,),
                reason="prompt is empty",
                sanitized=sanitized,
            )

        if len(sanitized) > self._max_length:
            categories.append(_CAT_TOO_LONG)

        if _any_match(_INJECTION_PATTERNS, sanitized):
            categories.append(_CAT_PROMPT_INJECTION)
        if _any_match(_JAILBREAK_PATTERNS, sanitized):
            categories.append(_CAT_JAILBREAK)
        if _any_match(_SQL_PATTERNS, sanitized):
            categories.append(_CAT_SQL_INJECTION)

        safe = len(categories) == 0
        reason = None if safe else self._describe(categories)
        return ScanResult(
            safe=safe,
            categories=tuple(categories),
            reason=reason,
            sanitized=sanitized,
        )

    def enforce(self, text: str) -> str:
        """Return the sanitized prompt, or raise :class:`UnsafePromptError`.

        Fail-closed entry point for the request path: if it returns, the prompt
        is safe to send to the LLM. The raised error carries the full
        :class:`ScanResult` on ``.result``.
        """
        # Imported lazily to avoid a circular import (errors imports ScanResult
        # only under TYPE_CHECKING).
        from .errors import UnsafePromptError

        result = self.scan(text)
        if not result.safe:
            raise UnsafePromptError(result)
        return result.sanitized

    # ----------------------------------------------------------------- #
    # Internal helpers
    # ----------------------------------------------------------------- #
    @staticmethod
    def _sanitize(text: str) -> str:
        """Trim and collapse whitespace.

        Collapsing runs of whitespace both normalises the prompt for the LLM and
        defeats simple evasion where an attack phrase is spread across many
        spaces/newlines to dodge naive substring checks.
        """
        return _WHITESPACE_RE.sub(" ", text).strip()

    @staticmethod
    def _describe(categories: list[str]) -> str:
        """Build a human-readable reason from matched categories."""
        labels = {
            _CAT_PROMPT_INJECTION: "prompt-injection phrasing",
            _CAT_JAILBREAK: "jailbreak / role-hijack phrasing",
            _CAT_SQL_INJECTION: "embedded SQL/DDL",
            _CAT_TOO_LONG: "prompt exceeds maximum length",
            _CAT_EMPTY: "prompt is empty",
        }
        return "unsafe prompt: " + "; ".join(labels[c] for c in categories)


def scan_input(text: str, max_length: int = 2000) -> ScanResult:
    """Module-level convenience wrapper around :meth:`PromptGuard.scan`.

    Constructs a one-off :class:`PromptGuard` with ``max_length`` and scans
    ``text``. Handy for callers that do not want to hold a guard instance.
    """
    return PromptGuard(max_length=max_length).scan(text)


def _any_match(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    """Return ``True`` if any pattern in ``patterns`` matches ``text``."""
    return any(pattern.search(text) for pattern in patterns)
