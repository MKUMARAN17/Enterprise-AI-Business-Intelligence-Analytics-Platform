"""bi-llm — multi-provider, JSON-structured LLM routing for the BI agents.

    from bi_llm import JsonTaskRouter, TaskRoute, PromptBuilder, OfflineCompleter

    router = JsonTaskRouter(
        completers={"offline": OfflineCompleter()},
        routes={"intent": TaskRoute("offline", "n/a", required_keys=("intent", "domain"))},
        prompts=PromptBuilder.from_yaml("prompts/agent_prompts.yaml"),
    )
    result = router.run("intent", question="show collections")   # -> validated dict

Production registers ``OpenAICompleter`` instances (OpenAI + Gemini's
OpenAI-compatible endpoint); dev/CI registers a single ``OfflineCompleter`` so the
graph runs with no API key and no spend.
"""
from __future__ import annotations

from bi_llm.completers import ChatCompleter, OfflineCompleter, OpenAICompleter
from bi_llm.prompts import PromptBuilder, RenderedPrompt
from bi_llm.router import JsonTaskRouter, TaskRoute

__version__ = "0.1.0"

__all__ = [
    "JsonTaskRouter",
    "TaskRoute",
    "PromptBuilder",
    "RenderedPrompt",
    "ChatCompleter",
    "OpenAICompleter",
    "OfflineCompleter",
    "__version__",
]
