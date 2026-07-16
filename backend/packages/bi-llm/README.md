# bi-llm

Multi-provider, JSON-structured LLM routing for the BI agents.

```python
from bi_llm import JsonTaskRouter, TaskRoute, PromptBuilder, OfflineCompleter, OpenAICompleter

router = JsonTaskRouter(
    completers={"openai": OpenAICompleter(api_key=..., model="gpt-4o-mini"),
                "gemini": OpenAICompleter(api_key=..., model="gemini-1.5-pro",
                                          base_url="https://generativelanguage.googleapis.com/v1beta/openai/")},
    routes={"intent": TaskRoute("gemini", "gemini-1.5-flash", required_keys=("intent","domain"))},
    prompts=PromptBuilder.from_yaml("prompts/agent_prompts.yaml"),
)
router.run("intent", question="show total collections this month")   # -> validated dict
```

- **Prompts live in YAML** (`PromptBuilder.from_yaml`) — tune without a deploy.
- Each task routes to a provider/model and declares `required_keys`; the router retries once on malformed JSON, then raises `AgentError` (fail-closed).
- **`OfflineCompleter`** is a deterministic, network-free completer so the graph runs end-to-end in CI/dev with no API key. Prod swaps in `OpenAICompleter` at the composition root. Gemini is reached via its OpenAI-compatible endpoint (a different `base_url`).
