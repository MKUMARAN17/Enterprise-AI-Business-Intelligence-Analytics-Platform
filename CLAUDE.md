# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Repo shape

Monorepo. The app lives in `backend/enterprise_bi`; the reusable platform layers
live in `backend/packages/bi-*` and resolve as **editable path-deps** (see
`[tool.uv.sources]` in `backend/pyproject.toml`). Package name `bi-xxx` (dist) ↔
`bi_xxx` (import). Each package owns its `pyproject.toml`, `errors.py`, `tests/`,
and `__init__.py` (`__version__` + `__all__`).

- `backend/enterprise_bi/` — FastAPI + the 7-agent LangGraph.
- `backend/packages/` — `bi-base, bi-auth, bi-llm, bi-data, bi-guardrails,
  bi-sql-guard, bi-schema-rag, bi-viz, bi-reports`.
- `backend/sql/` — the MySQL dump (`01_schema.sql` + `02_seed.sql`), **all
  identifiers UPPERCASE**.
- `changelog/changelog.md` — append a dated entry after every code change.

## Commands (`cd backend`)

```bash
pip install -e ".[dev]"      # + each packages/bi-* editable (see README)
pytest                       # full suite; runs with no MySQL and no API key
ruff check .                 # E/F/I/W/UP/B/SIM, line-length 100, E501 ignored
uvicorn enterprise_bi.app.main:app     # prod ASGI (composition root from Settings)
python scripts/gen_seed.py > sql/02_seed.sql   # regenerate deterministic seed
python scripts/mint_dev_token.py --role BUSINESS_ANALYST
```

## Architecture — one turn

`app/main.py` → `build_orchestration_service(settings)` (composition root) →
`create_app(settings, service=...)`. The service is stashed on
`app.state.orchestration_service`; the route resolves it.

`orchestration/service.py::OrchestrationService.handle_turn` binds request
context, runs the compiled graph (built once in `__post_init__` via
`orchestration/builder.py::build_graph(deps)`), times it, exports a report if
asked, and writes one `AUDIT_LOG` row. The graph mounts nine nodes
(`orchestration/agents/*`): guardrail → intent → schema → sql → validate →
execute → analytics → viz → insight, with conditional short-circuits on
guardrail-BLOCKED, validate-BLOCKED, execute-ERROR. **Node names carry an
`_agent` suffix** because LangGraph forbids a node named the same as a state key.

## Conventions worth knowing before editing

- **UPPERCASE identifiers everywhere.** Schema, seed, RAG catalog, generated SQL,
  and `Dataset.columns` are all UPPERCASE. Don't introduce lowercase table/column
  names — the RAG context and the SQL guard's allow-list assume the convention.
- **Fail closed.** Boot raises `ConfigError` on missing config; auth raises
  `AuthError` on any token problem; the SQL guard raises on any non-SELECT. Do not
  add fallbacks that let the process serve a turn without its dependencies.
- **The LLM is never trusted for numbers.** The analytics agent computes KPIs in
  Python; the insight agent only *explains* those computed facts. Keep maths out
  of prompts.
- **Offline by default.** With no API key the router uses `OfflineCompleter`
  (deterministic). Tests rely on this — don't make a real network call a hard
  requirement of the graph.
- **Security is layered** (JWT → RBAC allow-list → prompt guardrails → SQL guard →
  read-only rolled-back execution → audit). Every generated query passes the guard
  scoped to `RbacPolicy.allowed_tables(role)` before it touches the DB.
- **Packages stay framework-free** except the app. `bi-base`/`bi-auth`/etc. must
  import and unit-test without FastAPI.

## Changelog convention

`changelog/changelog.md` is append-only. Each entry: consecutive `Date:`/`Issue:`/
`Impact:`/`Fix:`/`Location:` lines (no blank lines within an entry; one blank line
between entries); `Location:` values are `- path` bullets. `Date:` is
`DD/MM/YYYY HH:MM` IST. No headings, no `---`, no git SHAs.
