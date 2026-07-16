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
