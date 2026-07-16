"""Prompt-guardrail node (runs first, before any LLM call).

Scans the raw user question for prompt-injection / jailbreak / embedded-SQL
attempts via :class:`bi_guardrails.PromptGuard`. If the prompt is unsafe it sets
``state['error']`` and marks the turn BLOCKED so the graph short-circuits to the
response node without ever invoking a model — the cheapest and safest place to
stop an attack. The sanitized text replaces the raw question downstream.
"""
from __future__ import annotations

from bi_base.logging import get_logger
from bi_guardrails import PromptGuard

from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_guardrail_node(max_length: int = 2000):
    guard = PromptGuard(max_length=max_length)

    def guardrail_node(state: BIState) -> dict:
        scan = guard.scan(state.get("question", ""))
        if not scan.safe:
            log.warning("agent.guardrail_blocked", categories=list(scan.categories))
            return {
                "status": "BLOCKED",
                "error": {
                    "code": "GUARDRAIL_BLOCKED",
                    "message": scan.reason or "prompt rejected by guardrails",
                    "categories": list(scan.categories),
                },
            }
        return {"question": scan.sanitized, "status": "OK"}

    return guardrail_node
