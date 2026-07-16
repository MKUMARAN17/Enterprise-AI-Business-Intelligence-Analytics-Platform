# bi-base

Foundation layer for the Enterprise BI platform. Framework-free (only `structlog`).

| Module | Provides |
|---|---|
| `errors` | `BiError` root + typed subclasses, `to_problem()` for the HTTP boundary |
| `context` | `bind_request` / `get_request_id` correlation ids (ContextVar) |
| `logging` | `configure_logging` + `get_logger` (JSON or console) |
| `structured` | `extract_json` / `require_keys` for LLM JSON-schema output |
| `timing` | `stopwatch()` → `EXECUTION_MS` |

```python
from bi_base import configure_logging, get_logger, bind_request

configure_logging(level="INFO", json_logs=True)
bind_request(user_id="analyst")
get_logger(__name__).info("boot.ok", component="app")
```
