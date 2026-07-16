"""Chat completers — the provider adapters behind the router.

All completers satisfy the same tiny :class:`ChatCompleter` protocol
(``complete(system, user, *, temperature, json_mode) -> str``) so the router is
provider-agnostic. Three concrete implementations:

  * :class:`OpenAICompleter` — OpenAI (and Gemini, reached through its
    OpenAI-compatible endpoint by passing a different ``base_url`` + key; the
    Gemini genai SDK is a doc-coding adapter, not a chat completer, so we use the
    OpenAI-compatible surface for chat — same pattern as the reference platform).
  * :class:`OfflineCompleter` — a deterministic, network-free completer used when
    no API key is configured. It is NOT a language model: it inspects the task
    label + user text and returns canned, schema-shaped JSON so the whole graph
    runs end-to-end in CI and local dev. This is what keeps the platform testable
    without spend, while production swaps in the real provider at the composition
    root.
"""
from __future__ import annotations

import json
import re
from typing import Protocol, runtime_checkable

from bi_base.errors import AgentError
from bi_base.logging import get_logger

log = get_logger(__name__)


@runtime_checkable
class ChatCompleter(Protocol):
    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, json_mode: bool = True
    ) -> str: ...


class OpenAICompleter:
    """OpenAI-compatible chat completions (OpenAI or Gemini's compat endpoint)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dep
            raise AgentError("openai package not installed; add the [openai] extra") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._model = model

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, json_mode: bool = True
    ) -> str:
        kwargs: dict = {
            "model": self._model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - provider errors vary
            log.warning("llm.provider_error", error=str(exc)[:200])
            raise AgentError("LLM provider call failed") from exc
        return resp.choices[0].message.content or ""


class OfflineCompleter:
    """Deterministic, network-free completer for boot/dev/CI without API keys.

    It pattern-matches the task label embedded in the system prompt and the user
    question to emit plausible, schema-correct JSON. It intentionally covers the
    four structured tasks the graph relies on (intent / sql_plan / analysis /
    insight); anything else returns an empty object so ``require_keys`` fails
    loudly rather than silently.
    """

    _MONEY_METRICS = {
        "collection": "COLLECTIONS",
        "revenue": "REVENUE",
        "sales": "SALES",
        "claim": "CLAIMS",
        "payment": "PAYMENTS",
    }

    def complete(
        self, system: str, user: str, *, temperature: float = 0.0, json_mode: bool = True
    ) -> str:
        task = self._task_of(system)
        u = user.lower()
        if task == "intent":
            return json.dumps(self._intent(u))
        if task == "sql_plan":
            return json.dumps(self._sql_plan(user))
        if task == "analysis":
            return json.dumps({"kpis": [], "observations": ["offline-analysis"]})
        if task == "insight":
            return json.dumps(
                {
                    "summary": "Offline insight: results returned successfully.",
                    "highlights": [],
                    "recommendations": [],
                }
            )
        return "{}"

    @staticmethod
    def _task_of(system: str) -> str:
        m = re.search(r"TASK:\s*([a-z_]+)", system)
        return m.group(1) if m else ""

    def _intent(self, u: str) -> dict:
        domain = "COLLECTIONS"
        for kw, tbl in self._MONEY_METRICS.items():
            if kw in u:
                domain = tbl
                break
        if "employee" in u or "performer" in u:
            domain = "EMPLOYEE_PERFORMANCE"
        wants_export = any(w in u for w in ("export", "excel", "csv", "pdf", "download"))
        return {
            "intent": "analytics_query",
            "domain": domain,
            "wants_export": wants_export,
            "wants_dashboard": "dashboard" in u,
            "metrics": ["amount"],
        }

    def _sql_plan(self, user: str) -> dict:
        # Key the plan off the explicit DOMAIN marker (resolved by the intent
        # agent) so schema-context text mentioning other tables can't skew the
        # choice; fall back to scanning the question when no marker is present.
        domain_match = re.search(r"DOMAIN:\s*([A-Z_]+)", user)
        u = (domain_match.group(1) if domain_match else user).lower()
        # A safe, generic aggregate that runs against the seed schema.
        if "revenue" in u:
            sql = (
                "SELECT B.BRANCH_NAME, R.REVENUE_MONTH, SUM(R.REVENUE_AMOUNT) AS TOTAL_REVENUE "
                "FROM REVENUE R JOIN BRANCHES B ON R.BRANCH_ID = B.BRANCH_ID "
                "GROUP BY B.BRANCH_NAME, R.REVENUE_MONTH ORDER BY R.REVENUE_MONTH"
            )
            tables = ["REVENUE", "BRANCHES"]
        elif "employee" in u or "performer" in u:
            sql = (
                "SELECT E.EMPLOYEE_NAME, P.FISCAL_QUARTER, SUM(P.SALES_ACHIEVED) AS ACHIEVED "
                "FROM EMPLOYEE_PERFORMANCE P JOIN EMPLOYEES E ON P.EMPLOYEE_ID = E.EMPLOYEE_ID "
                "GROUP BY E.EMPLOYEE_NAME, P.FISCAL_QUARTER ORDER BY ACHIEVED DESC"
            )
            tables = ["EMPLOYEE_PERFORMANCE", "EMPLOYEES"]
        else:
            sql = (
                "SELECT B.BRANCH_NAME, SUM(C.COLLECTION_AMOUNT) AS TOTAL_COLLECTIONS "
                "FROM COLLECTIONS C JOIN BRANCHES B ON C.BRANCH_ID = B.BRANCH_ID "
                "GROUP BY B.BRANCH_NAME ORDER BY TOTAL_COLLECTIONS DESC"
            )
            tables = ["COLLECTIONS", "BRANCHES"]
        return {"sql": sql, "tables": tables, "rationale": "offline deterministic plan"}
