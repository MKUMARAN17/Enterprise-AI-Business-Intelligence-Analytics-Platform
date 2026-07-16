"""JsonTaskRouter — the single entry point the agents use to call an LLM.

Responsibilities:
  * pick the provider/model for a given task from the routing config (so cheap
    tasks like intent classification can use a small model while SQL generation
    uses a stronger one),
  * render the task's prompt via the PromptBuilder,
  * call the selected ChatCompleter,
  * parse + shallow-validate the JSON against the task's required keys, retrying
    once on a malformed response before giving up.

The router owns one completer per provider id, injected at construction. In prod
the composition root passes real OpenAICompleters; in dev/CI it passes a single
OfflineCompleter registered under every provider id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bi_base.errors import AgentError
from bi_base.logging import get_logger
from bi_base.structured import extract_json, require_keys

from bi_llm.completers import ChatCompleter
from bi_llm.prompts import PromptBuilder

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TaskRoute:
    provider: str
    model: str
    temperature: float = 0.0
    required_keys: tuple[str, ...] = ()


class JsonTaskRouter:
    def __init__(
        self,
        *,
        completers: dict[str, ChatCompleter],
        routes: dict[str, TaskRoute],
        prompts: PromptBuilder,
        max_retries: int = 1,
    ):
        if not completers:
            raise AgentError("JsonTaskRouter needs at least one completer")
        self._completers = completers
        self._routes = routes
        self._prompts = prompts
        self._max_retries = max_retries

    def run(self, task: str, **variables) -> dict[str, Any]:
        route = self._routes.get(task)
        if route is None:
            raise AgentError(f"no route configured for task {task!r}")
        completer = self._completers.get(route.provider)
        if completer is None:
            raise AgentError(f"no completer for provider {route.provider!r}")

        prompt = self._prompts.render(task, **variables)
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            raw = completer.complete(
                prompt.system, prompt.user, temperature=route.temperature, json_mode=True
            )
            try:
                obj = extract_json(raw)
                if route.required_keys:
                    require_keys(obj, list(route.required_keys))
                log.info("llm.task_ok", task=task, provider=route.provider, attempt=attempt)
                return obj
            except Exception as exc:  # noqa: BLE001 - retry any parse/validation failure
                last_error = exc
                log.warning("llm.task_retry", task=task, attempt=attempt, error=str(exc)[:200])
        raise AgentError(f"task {task!r} produced no valid JSON") from last_error
