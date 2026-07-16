"""Agent 1 — Intent Agent.

Understands the user request: the business domain, the metrics involved, and
whether the user wants an export or a dashboard. It is the first LLM step and its
output steers the rest of the graph (domain feeds schema retrieval; wants_export
feeds the report stage). Conversation ``history`` is passed so follow-ups
("filter only Chennai", "compare with last year") resolve against prior turns.
"""
from __future__ import annotations

from bi_base.logging import get_logger

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.state import BIState

log = get_logger(__name__)


def make_intent_node(deps: GraphDeps):
    def intent_node(state: BIState) -> dict:
        history = _format_history(state.get("history", []))
        result = deps.router.run(
            "intent",
            question=state["question"],
            history=history,
        )
        log.info("agent.intent", domain=result.get("domain"), export=result.get("wants_export"))
        return {
            "intent": result,
            "export_format": _export_format(result),
        }

    return intent_node


def _export_format(intent: dict) -> str | None:
    if not intent.get("wants_export"):
        return None
    fmt = str(intent.get("export_format", "excel")).lower()
    return fmt if fmt in {"excel", "csv", "pdf"} else "excel"


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(no prior turns)"
    return "\n".join(f"USER: {h.get('question', '')}" for h in history[-5:])
