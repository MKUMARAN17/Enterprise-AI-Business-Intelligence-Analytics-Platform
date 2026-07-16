"""Shared fixtures: a seeded in-memory SQLite DB + a real OrchestrationService
composed over the OfflineCompleter, so the whole 7-agent graph runs end-to-end
in CI with no MySQL, no API key, and no network.

The offline SQL plans emit UPPERCASE-identifier queries; SQLite is
case-insensitive on identifiers, so the same generated SQL runs against this test
schema and against the real MySQL dump."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from bi_auth import Identity, RbacPolicy, Role
from bi_data import AuditLogWriter, QueryRunner
from bi_llm import JsonTaskRouter, OfflineCompleter, PromptBuilder, TaskRoute
from bi_schema_rag import SchemaIndex, SchemaRetriever, default_catalog

from enterprise_bi.orchestration.deps import GraphDeps
from enterprise_bi.orchestration.service import OrchestrationService

_PROMPTS = {
    "intent": {"system": "classify", "user": "{question}"},
    "sql_plan": {"system": "sql", "user": "DOMAIN: {domain}\n{question} {schema} {allowed_tables}"},
    "insight": {"system": "insight", "user": "{question} {kpis} {observations} {preview}"},
}


def _seed(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE BRANCHES (BRANCH_ID INT, BRANCH_NAME TEXT, STATE TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE COLLECTIONS (COLLECTION_ID INT, BRANCH_ID INT, "
                "COLLECTION_MONTH TEXT, COLLECTION_AMOUNT REAL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE REVENUE (REVENUE_ID INT, BRANCH_ID INT, REVENUE_MONTH TEXT, REVENUE_AMOUNT REAL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE EMPLOYEES (EMPLOYEE_ID INT, EMPLOYEE_NAME TEXT, BRANCH_ID INT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE EMPLOYEE_PERFORMANCE (PERFORMANCE_ID INT, EMPLOYEE_ID INT, "
                "FISCAL_QUARTER TEXT, SALES_ACHIEVED REAL)"
            )
        )
        conn.execute(
            text(
                """CREATE TABLE AUDIT_LOG (USER_ID TEXT, USERNAME TEXT, ROLE_NAME TEXT,
                REQUEST_ID TEXT, PROMPT TEXT, GENERATED_SQL TEXT, INTENT TEXT, EXECUTION_MS INT,
                ROW_COUNT INT, CHART_KIND TEXT, REPORT_FORMAT TEXT, STATUS TEXT, ERROR_MESSAGE TEXT)"""
            )
        )
        conn.execute(
            text("INSERT INTO BRANCHES VALUES (1,'Chennai Central','Tamil Nadu'),(2,'Bangalore Whitefield','Karnataka'),(3,'Kochi Marine Drive','Kerala')")
        )
        months = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
        cid = 0
        for b in (1, 2, 3):
            for mi, m in enumerate(months):
                cid += 1
                amt = 100000 + b * 10000 + mi * 5000
                conn.execute(
                    text("INSERT INTO COLLECTIONS VALUES (:i,:b,:m,:a)"),
                    {"i": cid, "b": b, "m": m, "a": amt},
                )
                conn.execute(
                    text("INSERT INTO REVENUE VALUES (:i,:b,:m,:a)"),
                    {"i": cid, "b": b, "m": m, "a": amt * 1.5},
                )
        conn.execute(text("INSERT INTO EMPLOYEES VALUES (1,'Employee 001',1),(2,'Employee 002',2)"))
        conn.execute(
            text(
                "INSERT INTO EMPLOYEE_PERFORMANCE VALUES (1,1,'Q1',500000),(2,1,'Q2',600000),(3,2,'Q1',400000),(4,2,'Q2',450000)"
            )
        )


@pytest.fixture
def engine():
    # StaticPool + shared connection so every checkout sees the same in-memory DB
    # (a plain :memory: engine gives each connection its own empty database).
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _seed(eng)
    return eng


@pytest.fixture
def service(engine) -> OrchestrationService:
    router = JsonTaskRouter(
        completers={"offline": OfflineCompleter()},
        routes={
            "intent": TaskRoute("offline", "n/a", required_keys=("intent", "domain", "wants_export")),
            "sql_plan": TaskRoute("offline", "n/a", required_keys=("sql", "tables")),
            "insight": TaskRoute("offline", "n/a", required_keys=("summary",)),
        },
        prompts=PromptBuilder(_PROMPTS),
    )
    tables, glossary = default_catalog()
    retriever = SchemaRetriever(SchemaIndex.build(tables, glossary))
    deps = GraphDeps(
        router=router,
        retriever=retriever,
        rbac=RbacPolicy(),
        query_runner=QueryRunner(engine),
        max_rows=1000,
    )
    return OrchestrationService(deps=deps, rbac=RbacPolicy(), audit=AuditLogWriter(engine))


@pytest.fixture
def analyst() -> Identity:
    return Identity(user_id="1", username="analyst", role=Role.BUSINESS_ANALYST)


@pytest.fixture
def sales_user() -> Identity:
    return Identity(user_id="4", username="sales", role=Role.SALES)
