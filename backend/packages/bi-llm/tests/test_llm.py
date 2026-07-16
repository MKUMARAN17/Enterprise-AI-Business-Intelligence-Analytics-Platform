from __future__ import annotations

import pytest
from bi_base.errors import AgentError

from bi_llm import JsonTaskRouter, OfflineCompleter, PromptBuilder, TaskRoute

CATALOG = {
    "intent": {
        "version": "1",
        "system": "You classify BI questions.",
        "user": "{question}",
    },
    "sql_plan": {
        "version": "1",
        "system": "You write MySQL.",
        "user": "Question: {question}\nSchema:\n{schema}",
    },
}


def _router() -> JsonTaskRouter:
    return JsonTaskRouter(
        completers={"offline": OfflineCompleter()},
        routes={
            "intent": TaskRoute("offline", "n/a", required_keys=("intent", "domain", "wants_export")),
            "sql_plan": TaskRoute("offline", "n/a", required_keys=("sql", "tables")),
        },
        prompts=PromptBuilder(CATALOG),
    )


def test_intent_task_returns_validated_json():
    out = _router().run("intent", question="show total collections this month")
    assert out["intent"] == "analytics_query"
    assert out["domain"] == "COLLECTIONS"
    assert out["wants_export"] is False


def test_intent_detects_export_and_domain():
    out = _router().run("intent", question="export revenue report to excel")
    assert out["domain"] == "REVENUE"
    assert out["wants_export"] is True


def test_sql_plan_returns_select():
    out = _router().run("sql_plan", question="top branches by collections", schema="...")
    assert out["sql"].upper().startswith("SELECT")
    assert "COLLECTIONS" in out["tables"]


def test_unknown_task_raises():
    with pytest.raises(AgentError):
        _router().run("nonexistent", question="x")


def test_prompt_builder_injects_task_marker():
    pb = PromptBuilder(CATALOG)
    rp = pb.render("intent", question="hi")
    assert rp.system.startswith("TASK: intent")
    assert rp.user == "hi"


def test_missing_required_key_raises(monkeypatch):
    router = JsonTaskRouter(
        completers={"offline": OfflineCompleter()},
        routes={"intent": TaskRoute("offline", "n/a", required_keys=("nonexistent_key",))},
        prompts=PromptBuilder(CATALOG),
        max_retries=0,
    )
    with pytest.raises(AgentError):
        router.run("intent", question="show collections")
