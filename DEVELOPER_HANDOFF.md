# Developer Handoff — Enterprise AI Business Intelligence & Analytics Platform

> Everything a new engineer needs to own this service: what it does, how it is
> built, why each decision was made, how to run/extend it, and where the sharp
> edges are. Read this top-to-bottom once; after that use it as a reference.

---

## 1. What this project is

An **AI Business Analyst**. A business user (analyst, manager, finance, sales)
asks a question in plain English — *"show collection performance for the last six
months"* — and the platform returns a **business summary + a data table + a chart
+ an optional Excel/PDF/CSV export**, with zero SQL knowledge required.

It replaces the manual loop (analyst → raise request → developer writes SQL →
export Excel → build charts → send report) with a single API call that a
multi-agent AI pipeline answers in seconds.

**One-line technical description:** a natural-language-to-SQL BI service built as a
9-node **LangGraph** over MySQL, wrapped in FastAPI, standing on nine
independently-versioned `bi-*` Python packages, with layered security (JWT → RBAC
→ prompt guardrails → SQL guard → read-only execution → audit).

---

## 2. Mental model — one request, end to end

```
                       POST /api/v1/ask   { "question": "...", "history": [...] }
                              │  Authorization: Bearer <JWT>
                              ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  HTTP boundary (enterprise_bi/api/routes.py)                  │
        │   • auth_dep validates JWT → Identity (user_id, role)         │
        │   • mint request_id, call OrchestrationService.handle_turn    │
        └─────────────────────────────────────────────────────────────┘
                              ▼
        OrchestrationService.handle_turn  (orchestration/service.py)
          • bind request context (correlation id in every log line)
          • allowed_tables = RbacPolicy.allowed_tables(role)
          • run the compiled graph, timed with a stopwatch
          • optionally export a report, write ONE AUDIT_LOG row
                              ▼
        ┌──────────────── LangGraph (orchestration/builder.py) ─────────────────┐
        │ guardrail_agent   prompt-injection scan   ── unsafe ─────────────► END │
        │      ▼                                                                 │
        │ intent_agent      LLM: domain, metrics, wants_export                   │
        │      ▼                                                                 │
        │ schema_agent      RAG: retrieve relevant tables (∩ allowed_tables)     │
        │      ▼                                                                 │
        │ sql_agent         LLM: generate ONE MySQL SELECT (JSON plan)           │
        │      ▼                                                                 │
        │ validate_agent    SQL guard + RBAC allow-list  ── blocked ───────► END │
        │      ▼                                                                 │
        │ execute_agent     read-only, rolled-back query  ── error ───────► END  │
        │      ▼                                                                 │
        │ analytics_agent   compute KPIs in Python (exact, not LLM)              │
        │      ▼                                                                 │
        │ viz_agent         choose chart, emit Vega-Lite spec                    │
        │      ▼                                                                 │
        │ insight_agent     LLM: business narrative grounded in the KPIs         │
        │      ▼                                                                 │
        │     END → assembled response                                          │
        └────────────────────────────────────────────────────────────────────┘
                              ▼
        AskResponse  { status, intent, generated_sql, columns, rows, row_count,
                       analytics, visualization, insight, export, execution_ms }
```

The two conditional short-circuits are the safety spine: **a prompt that fails the
guardrail never reaches an LLM, and SQL that fails the validator never reaches the
database.**

---

## 3. Repository layout

```
enterprise-ai-bi-platform/
├── backend/
│   ├── enterprise_bi/                 # THE APP
│   │   ├── app/
│   │   │   ├── main.py                # ASGI entrypoint (uvicorn target)
│   │   │   ├── factory.py             # create_app(): FastAPI + CORS + auth gate + routes
│   │   │   └── composition.py         # composition root: Settings → wired collaborators
│   │   ├── api/
│   │   │   ├── routes.py              # POST /api/v1/ask
│   │   │   └── models.py              # AskRequest / AskResponse (pydantic)
│   │   ├── auth_dep.py                # FastAPI JWT dependency (thin adapter over bi-auth)
│   │   ├── config/settings.py         # Settings (pydantic-settings, env prefix BI_)
│   │   └── orchestration/
│   │       ├── state.py               # BIState (the TypedDict flowing through the graph)
│   │       ├── deps.py                # GraphDeps (collaborator bundle for the nodes)
│   │       ├── builder.py             # build_graph(deps) → compiled LangGraph
│   │       ├── service.py             # OrchestrationService.handle_turn (the entrypoint)
│   │       └── agents/                # the 9 node factories (make_*_node)
│   ├── packages/                      # OUR OWN PLATFORM PACKAGES (editable path-deps)
│   │   ├── bi-base/                   # logging, errors, request context, structured output
│   │   ├── bi-auth/                   # JWT validation + RBAC
│   │   ├── bi-llm/                    # JsonTaskRouter (OpenAI/Gemini) + offline completer
│   │   ├── bi-guardrails/             # prompt-injection / jailbreak detection
│   │   ├── bi-schema-rag/             # FAISS + glossary schema retrieval (RAG)
│   │   ├── bi-sql-guard/              # SQL validation (SELECT-only, allow-list)
│   │   ├── bi-data/                   # read-only SQLAlchemy execution + audit writer
│   │   ├── bi-viz/                    # chart selection → Vega-Lite spec
│   │   └── bi-reports/                # Excel / PDF / CSV export
│   ├── sql/
│   │   ├── 01_schema.sql              # MySQL DDL — ALL identifiers UPPERCASE
│   │   └── 02_seed.sql                # deterministic seed data
│   ├── prompts/agent_prompts.yaml     # prompt catalog (edit without a deploy)
│   ├── config/llm_routing.yaml        # per-task provider/model routing
│   ├── scripts/gen_seed.py            # regenerates 02_seed.sql deterministically
│   ├── scripts/mint_dev_token.py      # mint a dev JWT
│   ├── tests/                         # end-to-end graph + HTTP tests
│   └── pyproject.toml                 # app deps + [tool.uv.sources] path-deps
├── deploy/                            # Dockerfile, docker-compose.yml, nginx.conf
├── changelog/changelog.md
├── README.md · CLAUDE.md · DEVELOPER_HANDOFF.md (this file)
```

### Why the package system (the most important structural decision)
The reusable capabilities live in `backend/packages/bi-*`, each a real installable
package (`bi-xxx` dist name ↔ `bi_xxx` import name) resolved as an **editable
path-dep** via `[tool.uv.sources]` in `backend/pyproject.toml`. This mirrors the
reference `ai-billing-support-v2` platform layout. Benefits:

- **Framework isolation** — every `bi-*` package imports and unit-tests *without*
  FastAPI. Only the app knows about HTTP.
- **Clear seams** — each package has one job, a small public API (`__all__`), and
  its own `errors.py` + `tests/`.
- **Independent versioning** — bump `bi-sql-guard` without touching the app.

---

## 4. The nine platform packages (technical spec)

Every package: starts files with `from __future__ import annotations`, uses
`@dataclass(frozen=True, slots=True)` for data shapes, roots errors at a
`RuntimeError` subclass, exposes a curated `__all__`, and is `ruff`-clean
(line-length 100; E/F/I/W/UP/B/SIM).

### 4.1 `bi-base` — foundation (only third-party dep: `structlog`)
The layer everything else stands on; no domain logic.
- `configure_logging(level, json_logs)` / `get_logger(name)` — structured logging;
  JSON in prod, console in dev. Log with key/values, never f-strings.
- `bind_request(request_id, user_id)` / `get_request_id()` — a `ContextVar`
  correlation id auto-injected into every log line down the stack.
- `extract_json(text)` / `require_keys(obj, keys)` — coerce LLM output into JSON
  (handles bare objects, ```json fences, prose-embedded objects) and shallow-
  validate required keys. Raises `StructuredOutputError`.
- `stopwatch()` — context manager → `Elapsed.ms` (feeds `EXECUTION_MS`).
- Error hierarchy: `BiError` (root; `.code`, `.status_code`, `.to_problem()`) →
  `ConfigError`, `AuthError`, `AuthorizationError`, `GuardrailError`,
  `SqlSafetyError`, `QueryExecutionError`, `AgentError`.

### 4.2 `bi-auth` — authentication + RBAC (`pyjwt[crypto]`)
- `JwtValidator(secret=|public_key=, algorithms, audience, issuers, leeway_seconds)`
  `.validate(token) -> Identity`. **Fail-closed**: bad signature / expired / wrong
  audience / untrusted issuer / missing `role`|`sub` → `AuthError`. HS256 (dev
  secret) and RS256 (prod PEM) share one path.
- `Identity(user_id, username, role: Role, tenant, claims)` — frozen; minted only
  from a verified token.
- `Role` — `StrEnum` mirroring `ROLES.ROLE_NAME`: `BUSINESS_ANALYST`, `MANAGER`,
  `FINANCE`, `SALES`, `ADMIN`.
- `RbacPolicy.allowed_tables(role) -> set[str]` / `.can_read(role, table)` — the
  allow-list of UPPERCASE tables per role, handed to the SQL guard.
- `mint_dev_token(...)` — dev-only HS256 minting (also in `scripts/mint_dev_token.py`).

**RBAC grants** (`bi_auth/rbac.py`):
| Role | Tables |
|---|---|
| `ADMIN` | all business tables **+** `USERS`, `ROLES`, `AUDIT_LOG` |
| `BUSINESS_ANALYST`, `MANAGER` | all 14 business tables |
| `FINANCE` | REGIONS, BRANCHES, CUSTOMERS, CUSTOMER_ACCOUNTS, COLLECTIONS, REVENUE, CLAIMS, PAYMENTS |
| `SALES` | REGIONS, BRANCHES, PRODUCTS, CUSTOMERS, EMPLOYEES, EMPLOYEE_PERFORMANCE, COLLECTIONS, SALES, INVENTORY |

### 4.3 `bi-llm` — multi-provider JSON routing (`pyyaml`; `openai` optional)
- `JsonTaskRouter(completers, routes, prompts, max_retries=1).run(task, **vars) -> dict`
  — picks the provider/model for the task, renders the prompt, calls the completer,
  parses+validates JSON against `required_keys`, retries once on malformed output,
  then raises `AgentError`.
- `TaskRoute(provider, model, temperature, required_keys)`.
- `PromptBuilder.from_yaml(path)` — loads the prompt catalog; `.render(task, **vars)`
  injects a `TASK: <name>` marker + interpolates `{placeholders}`.
- Completers (all satisfy the `ChatCompleter` protocol):
  - `OpenAICompleter(api_key, model, base_url=None)` — OpenAI, and Gemini via its
    OpenAI-compatible endpoint (just a different `base_url`).
  - `OfflineCompleter()` — **deterministic, network-free**. Inspects the `TASK:`
    marker + text and returns canned schema-shaped JSON so the whole graph runs in
    CI/dev with no API key and no spend. It is NOT a model; prod swaps in the real
    provider at the composition root.

### 4.4 `bi-guardrails` — prompt safety (pure stdlib)
- `PromptGuard(max_length=2000).scan(text) -> ScanResult` / `.enforce(text) -> str`.
- `ScanResult(safe, categories, reason, sanitized)`; categories:
  `prompt_injection`, `jailbreak`, `sql_injection`, `too_long`, `empty`.
- `scan_input(text, max_length)` module helper; `UnsafePromptError` carries `.result`.

### 4.5 `bi-schema-rag` — schema retrieval / RAG (stdlib; FAISS optional)
- `default_catalog() -> (tables, glossary)` — 13 `TableDoc`s + 8 `GlossaryDoc`s
  describing the UPPERCASE schema (columns, FKs, business synonyms).
- `SchemaIndex.build(tables, glossary, embedder=None)` — embeds each doc. Uses
  FAISS `IndexFlatIP` + BAAI `bge-small-en-v1.5` **if installed**, else falls back
  to a deterministic stdlib `HashingEmbedder` + pure-Python cosine. **Runs
  stdlib-only** — ML deps are an optional accelerator.
- `SchemaRetriever(index).retrieve(query, k=6) -> list[RetrievedChunk]` — hybrid
  score (vector cosine + keyword-overlap boost). `.format_context(chunks)` renders
  a prompt-ready schema slice.

### 4.6 `bi-sql-guard` — SQL validation (pure stdlib) — **the security gate**
- `SqlGuard(allowed_tables=None, max_limit=10000)`
  `.validate(sql) -> GuardResult` (raises on violation — fail-closed) /
  `.try_validate(sql)` (returns `ok=False` instead of raising).
- `GuardResult(ok, statement_type, tables, reason, normalized_sql)`.
- Rules: strip comments first → reject empty → reject stacked statements → allow
  only `SELECT`/`WITH…SELECT` → scan whole token stream for destructive tokens
  (DROP/DELETE/…/`INTO OUTFILE`/`SLEEP(`/`BENCHMARK(`) → check table allow-list →
  append a safety `LIMIT`.
- Errors: `SqlGuardError`, `DestructiveStatementError`, `MultipleStatementsError`,
  `UnauthorizedTableError`, `EmptyStatementError`.

### 4.7 `bi-data` — data access + audit (`sqlalchemy`; `pymysql` optional)
- `QueryRunner.from_url(url)` / `.execute(sql, params, max_rows) -> Dataset`.
  Runs inside an **always-rolled-back** read-only transaction + a hard `fetchmany`
  cap → defence in depth behind the guard. Driver errors → `QueryExecutionError`
  (raw driver text never surfaced to the client).
- `Dataset(columns, rows)` — the canonical hand-off shape (UPPERCASE columns) with
  `row_count`, `is_empty`, `column_types()` (numeric/temporal/categorical),
  `to_records()`.
- `AuditLogWriter(engine).write(AuditEntry)` — commits ONE `AUDIT_LOG` row per turn
  on its own connection; never raises into the request path.

### 4.8 `bi-viz` — visualization (pure stdlib)
- `select_visualization(dataset, request_hint, top_n) -> VizChoice` — heuristics:
  temporal + "trend" → **line**; category + numeric + "compare/top/rank" → **bar**;
  "share/proportion" + few rows → **pie**; two numerics → **scatter**; else
  **table**.
- `VizChoice(kind, reason, spec, x, y)` — `spec` is a Vega-Lite v5 object with data
  inlined. `build_chart_spec(...)` exported too.

### 4.9 `bi-reports` — export (stdlib CSV; `openpyxl`/`reportlab` optional)
- `export(dataset, fmt, path, title="") -> ExportResult`; `fmt` ∈ `ExportFormat`
  (`csv`/`excel`/`pdf`). CSV always works (stdlib); Excel/PDF import lazily and
  raise `MissingDependencyError` if the engine is absent (never silently writes a
  wrong-format file).

---

## 5. The app internals

### 5.1 `BIState` (orchestration/state.py)
A `TypedDict(total=False)` merged node-to-node by LangGraph. Key groups: inputs
(`question`, `role`, `allowed_tables`, `history`), `intent`, `schema_context`/
`retrieved_tables`, `sql`/`validated_sql`, `columns`/`rows`/`row_count`,
`analytics`/`visualization`/`insight`, control (`error`, `status`,
`export_format`, `chart_kind`).

### 5.2 The nine node factories (orchestration/agents/)
Each `make_<x>_node(deps) -> (BIState) -> dict` closes over `GraphDeps`. Node names
in the graph carry an `_agent` suffix (see gotcha §9.1). Data-only nodes
(`analytics`, `execute`, `guardrail`, `viz`) do no LLM calls; the exact-maths
policy (§9.2) lives in `analytics_agent`.

### 5.3 Composition root (app/composition.py)
`build_orchestration_service(settings)`:
1. `QueryRunner.from_url(BI_DATABASE_URL)` (+ `AuditLogWriter` on the same engine).
2. `build_router(settings)` — real `OpenAICompleter`s when keys are set; otherwise
   one `OfflineCompleter` registered under every provider id. Routes/prompts loaded
   from `config/llm_routing.yaml` + `prompts/agent_prompts.yaml`.
3. `build_retriever()` — `SchemaIndex` over `default_catalog()`.
4. `RbacPolicy()`, assembled into `GraphDeps`, into `OrchestrationService` (which
   compiles the graph once in `__post_init__`).

Fails fast with `ConfigError` if `BI_DATABASE_URL` is missing — no half-wired boot.

### 5.4 HTTP surface
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | liveness |
| POST | `/api/v1/ask` | Bearer JWT | ask a question, get the full answer |

---

## 6. Data model (MySQL, UPPERCASE)

**Why UPPERCASE everywhere:** the generated SQL, the RAG schema context, and the
physical schema must line up with no case-folding ambiguity across engines. This is
a hard convention — do not introduce a lowercase identifier anywhere.

**Business tables:** `REGIONS, BRANCHES, PRODUCTS, CUSTOMERS, CUSTOMER_ACCOUNTS,
EMPLOYEES, EMPLOYEE_PERFORMANCE, COLLECTIONS, REVENUE, SALES, CLAIMS, PAYMENTS,
INVENTORY, PROCUREMENT`.
**Platform tables:** `USERS, ROLES, AUDIT_LOG`.

**Key relationships (FKs):**
```
REGIONS ─< BRANCHES ─< CUSTOMERS ─< CUSTOMER_ACCOUNTS
                     ├─< EMPLOYEES ─< EMPLOYEE_PERFORMANCE
                     ├─< COLLECTIONS >─ CUSTOMERS
                     ├─< REVENUE
                     ├─< SALES >─ PRODUCTS
                     ├─< CLAIMS ─< PAYMENTS
                     ├─< INVENTORY >─ PRODUCTS
                     └─< PROCUREMENT >─ PRODUCTS
ROLES ─< USERS      ;   AUDIT_LOG (standalone: user, prompt, sql, ms, chart, export)
```
Trend queries use pre-computed `COLLECTION_MONTH` / `REVENUE_MONTH` (`'YYYY-MM'`)
columns for cheap grouping. `AUDIT_LOG` satisfies the audit requirement (user,
prompt, generated SQL, execution time, chart kind, report format, status).

Regenerate the seed deterministically: `python scripts/gen_seed.py > sql/02_seed.sql`.

---

## 7. Configuration (env, prefix `BI_`)

All config comes from env / `.env` (never hard-coded). Full list in
`backend/.env.example`; the load-bearing ones:

| Variable | Meaning |
|---|---|
| `BI_DATABASE_URL` | `mysql+pymysql://user:pw@host:3306/ENTERPRISE_BI` (**required**) |
| `BI_JWT_SECRET` | HS256 dev secret (use ≥32 bytes) |
| `BI_JWT_PUBLIC_KEY_PATH` | RS256 PEM for prod (leave secret empty) |
| `BI_JWT_AUDIENCE` / `BI_JWT_ISSUERS` | token `aud` / trusted `iss` list |
| `BI_OPENAI_API_KEY` / `BI_GEMINI_API_KEY` | leave **empty → OfflineCompleter** |
| `BI_MAX_ROWS` | hard result cap (default 10000) |
| `BI_GUARDRAIL_MAX_LENGTH` | max prompt length |
| `BI_EXPORT_DIR` | where exports are written |
| `BI_REDIS_URL` | conversation memory (follow-ups) |

YAML config: `prompts/agent_prompts.yaml` (prompt catalog — tune without a deploy)
and `config/llm_routing.yaml` (per-task provider/model + `required_keys`).

---

## 8. Running, testing, deploying

### Local dev (no MySQL, no API key)
```bash
cd backend
python -m venv .venv && . .venv/bin/activate
for p in bi-base bi-auth bi-llm bi-data bi-guardrails bi-sql-guard bi-schema-rag bi-viz bi-reports; do
  pip install -e packages/$p; done
pip install -e ".[dev]"
pytest          # 161 tests pass; the whole graph runs on the OfflineCompleter + SQLite
ruff check enterprise_bi packages
```

### Against MySQL
```bash
docker compose -f deploy/docker-compose.yml up -d db redis   # auto-loads sql/*.sql
export BI_DATABASE_URL="mysql+pymysql://bi:bi@localhost:3306/ENTERPRISE_BI"
export BI_JWT_SECRET="dev-secret-change-me-32-bytes-min"
uvicorn enterprise_bi.app.main:app --reload

TOKEN=$(python scripts/mint_dev_token.py --role BUSINESS_ANALYST)
curl -s localhost:8000/api/v1/ask -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"show total collections by branch"}' | jq
```

### Full stack
`docker compose -f deploy/docker-compose.yml up --build` brings up MySQL (loads the
CAPS dump), Redis, the backend (multi-worker uvicorn), and Nginx on `:8080`.

### Test topology
- Each package has its own `tests/` (unit).
- `backend/tests/` runs **real end-to-end turns** through the compiled graph over a
  seeded in-memory SQLite DB with the `OfflineCompleter` — covers the happy path,
  guardrail block, RBAC block (SALES→REVENUE), export, and audit persistence.

---

## 9. Design decisions & gotchas (read before editing)

1. **LangGraph node names must not equal state keys.** A node named `intent` clashes
   with the `intent` state channel and raises at compile time — hence the `_agent`
   suffix on every node in `builder.py`. Keep it.
2. **The LLM is never trusted for numbers.** `analytics_agent` computes all KPIs and
   period-over-period changes in Python; `insight_agent` only *explains* those
   computed facts. This prevents fabricated percentages. Do not move maths into a
   prompt.
3. **Offline-first.** With no API key the router uses `OfflineCompleter`. The offline
   SQL planner keys its plan off the explicit `DOMAIN:` marker (resolved by the
   intent agent), **not** the raw text — otherwise schema-context words leak into
   the decision. Tests depend on this; don't make a real network call a hard
   requirement of the graph.
4. **Security is layered — don't remove a layer thinking another covers it.**
   JWT (authn) → RBAC allow-list (authz, table-level) → prompt guardrails →
   SQL guard (SELECT-only + allow-list) → read-only rolled-back execution → audit.
   The guard is always scoped to `RbacPolicy.allowed_tables(role)`.
5. **`Result.keys()` in `bi-data/engine.py` is SQLAlchemy, not a dict** — iterating
   the `Result` directly yields rows, not column names (there's a `noqa: SIM118`).
6. **Tests use `StaticPool`** for in-memory SQLite so the seed survives across
   connections (a plain `:memory:` engine gives each connection an empty DB).
7. **Packages stay framework-free.** Anything importing FastAPI belongs in
   `enterprise_bi`, not in a `bi-*` package.
8. **`AuditEntry` is a slots dataclass** — persist it with `dataclasses.asdict`, not
   `__dict__`.

---

## 10. Extension recipes

- **Add a business table** → add DDL (UPPERCASE) to `01_schema.sql`, seed it in
  `gen_seed.py`, add a `TableDoc` to `bi_schema_rag/catalog.py`, and grant it to
  roles in `bi_auth/rbac.py`.
- **Add a role** → add to `Role` (`bi_auth/models.py`), add its grant set in
  `rbac.py`, seed it in `ROLES`.
- **Add an agent/node** → write `make_<x>_node(deps)` in `orchestration/agents/`,
  register it in `agents/__init__.py`, and wire it in `builder.py` (remember the
  `_agent` suffix). Extend `BIState` with any new keys.
- **Add a chart type** → extend `select_visualization` + `build_chart_spec` in
  `bi-viz`.
- **Add an export format** → extend `ExportFormat` + an exporter in `bi-reports`.
- **Retune a prompt** → edit `prompts/agent_prompts.yaml` (bump `version`); no code
  deploy. Change which model answers a task in `config/llm_routing.yaml`.
- **Wire real LLMs** → set `BI_OPENAI_API_KEY` / `BI_GEMINI_API_KEY`; the
  composition root swaps `OfflineCompleter` for `OpenAICompleter` automatically.

---

## 11. Status & roadmap

**Done:** the full pipeline, 9 packages, CAPS MySQL dump + deterministic seed,
layered security, audit logging, YAML-driven prompts/routing, offline mode,
161 passing tests, ruff-clean, Docker/compose/nginx, docs.

**Deliberately stubbed / next up:**
- **Conversation memory** — `history` flows through the graph and Redis config
  exists, but a persistent Redis-backed memory store for follow-ups (*"filter only
  Chennai" → "compare with last year"*) is not yet wired; today history is passed
  per request.
- **Dashboard generation** — the spec's "create dashboard for collections"
  (KPI cards + multiple charts) is a natural next node composing several `viz`
  outputs.
- **Real embeddings by default** — install the `[rag]` extra (FAISS + bge) and the
  retriever upgrades automatically; production should provision these.
- **Rate limiting** — add at the Nginx/ASGI layer (config placeholder exists).
- **`USERS.PASSWORD_HASH`** is a placeholder — auth is JWT-issued by the corporate
  IdP; there is no local password login path yet.
- **Evaluation** — Ragas/DeepEval harnesses (SQL quality, retrieval quality,
  insight quality) and LangSmith tracing are named in the spec and not yet added.

---

## 12. Quick file index

| I need to change… | Go to |
|---|---|
| the HTTP contract | `enterprise_bi/api/models.py`, `routes.py` |
| how a turn is orchestrated | `enterprise_bi/orchestration/service.py` |
| the graph shape / routing | `enterprise_bi/orchestration/builder.py` |
| an agent's behaviour | `enterprise_bi/orchestration/agents/*.py` |
| what gets wired at boot | `enterprise_bi/app/composition.py` |
| config / env vars | `enterprise_bi/config/settings.py`, `.env.example` |
| the database schema/seed | `sql/01_schema.sql`, `scripts/gen_seed.py` |
| SQL safety rules | `packages/bi-sql-guard/bi_sql_guard/guard.py` |
| who can read what | `packages/bi-auth/bi_auth/rbac.py` |
| prompts / model routing | `prompts/agent_prompts.yaml`, `config/llm_routing.yaml` |
| chart selection | `packages/bi-viz/bi_viz/selector.py` |
| deployment | `deploy/` |
```
