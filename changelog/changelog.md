Date: 16/07/2026 18:15
Issue: The platform had no web UI — business users could only reach the AI analyst through raw HTTP calls to POST /api/v1/ask with a hand-minted JWT, and there was no browser sign-in path.
Impact: A self-contained React web workspace now exists at frontend/, modelled on the reference tensaw-health-promptql-frontend stack (React 18, TypeScript, Vite, Tailwind, TanStack Query, axios, zod, recharts, react-router). Users sign in by picking a role, then ask questions in plain English and see the assembled answer — business insight + KPI cards, an auto-selected chart (line/bar/pie/scatter rendered with recharts from the backend's visualization.kind), the data table, an export badge, and the collapsible generated SQL. Blocked prompts (guardrail / SQL-guard / RBAC) and errors render as clear banners. The app typechecks and vite-builds clean; the full sign-in→ask flow was verified end-to-end against the backend on the offline LLM completer.
Fix: Built the frontend as a self-contained app (the reference's proprietary @tensaw/* design-system is replaced by an in-repo UI kit in src/components/ui/primitives.tsx): typed env (config/env.ts), an axios client with a bearer-token interceptor and RFC-7807 problem-details error mapping (api/client.ts) validating responses with zod schemas that mirror the backend contract (api/schemas.ts), a localStorage-backed AuthContext + RequireAuth guard, a role vocabulary mirroring bi_auth.Role, an AppLayout shell (top bar + side nav + theme toggle), a SignInPage role picker, and the AskWorkspace page composing ChartRenderer/ResultTable/InsightPanel/SqlPanel. To let the SPA authenticate in dev, added a dev-only backend endpoint POST /api/v1/dev/login (enterprise_bi/api/dev_routes.py) that mints an HS256 token for a chosen role, gated by the new BI_ALLOW_DEV_LOGIN setting and mounted in the app factory; updated backend .env/.env.example with the flag and a CORS allow-list for http://localhost:5174.
Location:
- enterprise-ai-bi-platform/frontend/
- enterprise-ai-bi-platform/backend/enterprise_bi/api/dev_routes.py
- enterprise-ai-bi-platform/backend/enterprise_bi/app/factory.py
- enterprise-ai-bi-platform/backend/enterprise_bi/config/settings.py
- enterprise-ai-bi-platform/backend/.env.example

Date: 16/07/2026 14:57
Issue: The seed dataset was small (COLLECTIONS ~480 but most other tables in the tens), so demos and manual testing had thin data across sales, claims, customers, and employees.
Impact: The seed now carries a richer dataset — up to ~500 rows in the primary fact tables and proportionally larger supporting tables (CUSTOMERS 96, EMPLOYEES 64, EMPLOYEE_PERFORMANCE 128, COLLECTIONS 480, SALES 480, CLAIMS 240, PAYMENTS 119, PROCUREMENT 80; ~1,939 rows total), with no table exceeding 500. The demo scenarios are preserved (June-2026 dip on Bangalore/Kolkata, Kerala branches, Chennai vs Bangalore, Q1/Q2 employee comparison) and the dump still parses as valid MySQL with all identifiers UPPERCASE.
Fix: Parameterised scripts/gen_seed.py with per-table volume constants (CUSTOMERS_PER_BRANCH=12, COLLECTION_CUSTOMERS_PER_BRANCH=5, EMPLOYEES_PER_BRANCH=8, SALES_PER_BRANCH=60, CLAIMS_PER_BRANCH=30, PROCUREMENT_PER_BRANCH=10). COLLECTIONS now uses a 5-customer subset per branch so it stays under the 500 cap despite the larger CUSTOMERS pool, keeping the 12-month trend intact. Regenerated sql/02_seed.sql from the updated generator.
Location:
- enterprise-ai-bi-platform/backend/scripts/gen_seed.py
- enterprise-ai-bi-platform/backend/sql/02_seed.sql

Date: 16/07/2026 13:33
Issue: The Enterprise AI Business Intelligence & Analytics Platform described in Enterprise_AI_Business_Intelligence_Platform.docx had no code — only a specification for a natural-language-to-SQL multi-agent BI service.
Impact: A production-standard backend now exists: business users authenticate with JWT and POST a plain-English question to /api/v1/ask; a nine-node LangGraph (guardrail, intent, schema-RAG, SQL generation, SQL validation, execution, analytics, visualization, insight) returns a business summary, a table, a Vega-Lite chart spec, and an optional Excel/PDF/CSV export, with every turn written to AUDIT_LOG. The whole graph runs end-to-end with no MySQL and no API key via a deterministic offline LLM completer; 161 tests pass.
Fix: Built a monorepo mirroring the tensaw ai-billing-support-v2 package system — an enterprise_bi app (FastAPI + composition root + orchestration service/builder/state + seven agents) standing on nine editable path-dep packages (bi-base, bi-auth, bi-llm, bi-data, bi-guardrails, bi-sql-guard, bi-schema-rag, bi-viz, bi-reports). Security is layered: fail-closed JWT (bi-auth), a role→allowed-tables RBAC allow-list handed to a SELECT-only SQL guard (bi-sql-guard), prompt-injection guardrails (bi-guardrails), and read-only always-rolled-back query execution (bi-data). Renamed graph nodes with an _agent suffix because LangGraph forbids a node named the same as a BIState key; keyed the offline SQL planner off the DOMAIN marker so schema-context text cannot skew plan selection; switched the audit writer to dataclasses.asdict for the slots dataclass; used a SQLAlchemy StaticPool in tests so the in-memory SQLite seed persists across connections.
Fix continued: Authored the MySQL dump sql/01_schema.sql + sql/02_seed.sql with every table and column name in UPPERCASE (REGIONS, BRANCHES, PRODUCTS, CUSTOMERS, CUSTOMER_ACCOUNTS, EMPLOYEES, EMPLOYEE_PERFORMANCE, COLLECTIONS, REVENUE, SALES, CLAIMS, PAYMENTS, INVENTORY, PROCUREMENT, plus platform tables USERS, ROLES, AUDIT_LOG), with deterministic seed data (scripts/gen_seed.py) shaped to answer the spec's example scenarios (6/12-month trends, Kerala filter, June revenue dip, Q1/Q2 employee comparison). Added Docker/compose/nginx deployment, .env.example, YAML prompt catalog + LLM routing, and README/CLAUDE.md.
Location:
- enterprise-ai-bi-platform/backend/sql/01_schema.sql
- enterprise-ai-bi-platform/backend/sql/02_seed.sql
- enterprise-ai-bi-platform/backend/scripts/gen_seed.py
- enterprise-ai-bi-platform/backend/scripts/mint_dev_token.py
- enterprise-ai-bi-platform/backend/enterprise_bi/
- enterprise-ai-bi-platform/backend/packages/
- enterprise-ai-bi-platform/backend/prompts/agent_prompts.yaml
- enterprise-ai-bi-platform/backend/config/llm_routing.yaml
- enterprise-ai-bi-platform/backend/tests/
- enterprise-ai-bi-platform/backend/pyproject.toml
- enterprise-ai-bi-platform/deploy/Dockerfile
- enterprise-ai-bi-platform/deploy/docker-compose.yml
- enterprise-ai-bi-platform/deploy/nginx.conf
- enterprise-ai-bi-platform/README.md
- enterprise-ai-bi-platform/CLAUDE.md
