# Enterprise AI Business Intelligence & Analytics Platform

An **AI Business Analyst**: business users ask questions in plain English and get
back a summary, a table, a chart, and an optional export — no SQL, no dashboards,
no waiting on a developer. Built as a **multi-agent LangGraph** over a set of
independently-versioned platform packages, standing on FastAPI + MySQL.

> "Show collection performance for the last six months." → the platform
> understands the request, retrieves the relevant schema (RAG), generates and
> **validates** SQL, executes it read-only, computes KPIs, picks the best chart,
> and writes a business insight.

## Repo shape

```
enterprise-ai-bi-platform/
├── backend/
│   ├── enterprise_bi/            # the app: FastAPI + the 7-agent LangGraph
│   │   ├── app/                  # main / factory / composition root
│   │   ├── orchestration/        # state, builder, service, agents/
│   │   ├── api/                  # /api/v1/ask contract
│   │   └── config/               # Settings (pydantic-settings)
│   ├── packages/                 # OUR OWN platform packages (editable path-deps)
│   │   ├── bi-base/              #   logging, errors, context, structured output
│   │   ├── bi-auth/              #   JWT validation + RBAC (role→allowed tables)
│   │   ├── bi-llm/               #   JsonTaskRouter (OpenAI/Gemini) + offline mode
│   │   ├── bi-guardrails/        #   prompt-injection detection
│   │   ├── bi-schema-rag/        #   FAISS + glossary schema retrieval (RAG)
│   │   ├── bi-sql-guard/         #   SQL validation (SELECT-only, allow-list)
│   │   ├── bi-data/              #   read-only SQLAlchemy execution + audit
│   │   ├── bi-viz/               #   chart selection → Vega-Lite spec
│   │   └── bi-reports/           #   Excel / PDF / CSV export
│   ├── sql/                      # MySQL dump — 01_schema.sql + 02_seed.sql (CAPS)
│   ├── prompts/ config/          # YAML prompt catalog + LLM routing
│   ├── scripts/                  # gen_seed.py, mint_dev_token.py
│   └── tests/                    # end-to-end graph + HTTP tests
├── deploy/                       # Dockerfile, docker-compose, nginx
└── changelog/changelog.md
```

## The seven agents (LangGraph)

```
POST /api/v1/ask  ──(JWT + RBAC)──▶ guardrail ─▶ intent ─▶ schema (RAG) ─▶ sql-gen
                                        │           │          │             │
                                    injection?   domain     table slice   MySQL SELECT
                                        ▼           ▼          ▼             ▼
                                     validate (SQL guard + RBAC allow-list) ◀┘
                                        │  blocked → END
                                        ▼
                                     execute (read-only, rolled back)
                                        │  error → END
                                        ▼
                                 analytics ─▶ visualization ─▶ insight ─▶ response
                                 (exact KPIs)  (best chart)   (business prose)
```

Two conditional short-circuits keep it safe and cheap: a prompt that fails the
**guardrail** never reaches an LLM, and SQL that fails the **validator** never
reaches the database.

## Security model (defence in depth)

1. **JWT** (`bi-auth`) — fail-closed; no anonymous path. Roles mirror
   `ROLES.ROLE_NAME`: `BUSINESS_ANALYST`, `MANAGER`, `FINANCE`, `SALES`, `ADMIN`.
2. **RBAC allow-list** — each role maps to a set of readable UPPERCASE tables;
   the set is handed to the SQL guard, so `SALES` cannot query `CLAIMS`.
3. **Prompt guardrails** (`bi-guardrails`) — injection / jailbreak / embedded-SQL.
4. **SQL guard** (`bi-sql-guard`) — SELECT-only, single statement, comment-stripped,
   no `INTO OUTFILE`/`SLEEP`/…, table allow-list, forced `LIMIT`.
5. **Read-only execution** (`bi-data`) — every analytical query runs in an
   always-rolled-back transaction with a hard row cap.
6. **Audit** — one `AUDIT_LOG` row per turn (user, prompt, SQL, ms, chart, export).

## Quick start (local, no API key)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ./packages/bi-base -e ./packages/bi-auth -e ./packages/bi-llm \
            -e ./packages/bi-data -e ./packages/bi-guardrails -e ./packages/bi-sql-guard \
            -e ./packages/bi-schema-rag -e ./packages/bi-viz -e ./packages/bi-reports
pip install -e ".[dev]"
pytest                                   # 161 tests, no MySQL / no API key needed
```

With no `BI_OPENAI_API_KEY`/`BI_GEMINI_API_KEY`, the LLM router uses the
deterministic **OfflineCompleter**, so the whole graph runs end-to-end for dev/CI.
Set a key in `.env` to switch to real Gemini/OpenAI.

### Run against MySQL

```bash
docker compose -f deploy/docker-compose.yml up -d db redis   # MySQL loads sql/*.sql on init
export BI_DATABASE_URL="mysql+pymysql://bi:bi@localhost:3306/ENTERPRISE_BI"
export BI_JWT_SECRET="dev-secret"
uvicorn enterprise_bi.app.main:app --reload

TOKEN=$(python scripts/mint_dev_token.py --role BUSINESS_ANALYST)
curl -s localhost:8000/api/v1/ask -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' \
     -d '{"question":"show total collections by branch"}' | jq
```

## SQL dump

`sql/01_schema.sql` + `sql/02_seed.sql` create the `ENTERPRISE_BI` database with
**every table and column name in UPPERCASE** (a hard platform convention so the
generated SQL, the RAG schema context, and the physical schema line up). Regenerate
the deterministic seed with `python scripts/gen_seed.py > sql/02_seed.sql`.

Tables: `REGIONS, BRANCHES, PRODUCTS, CUSTOMERS, CUSTOMER_ACCOUNTS, EMPLOYEES,
EMPLOYEE_PERFORMANCE, COLLECTIONS, REVENUE, SALES, CLAIMS, PAYMENTS, INVENTORY,
PROCUREMENT` + platform tables `USERS, ROLES, AUDIT_LOG`.

## Technology

Python 3.11 · FastAPI · LangGraph · LangChain-compatible LLM routing (Gemini/OpenAI)
· SQLAlchemy 2.0 · MySQL · FAISS + BAAI bge (optional) · Redis (memory) · JWT · RBAC
· structlog · Pydantic Settings · Docker · Nginx · pytest.
