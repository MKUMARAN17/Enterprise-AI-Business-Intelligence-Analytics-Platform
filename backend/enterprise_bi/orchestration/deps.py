"""The dependency bundle every agent node closes over.

Composed once at boot (see ``app/composition.py``) and passed to
``build_graph(deps)``. Holding the collaborators here — instead of importing
singletons — keeps the graph testable: a test builds a ``GraphDeps`` with fakes
and gets the exact same wiring the prod app runs.
"""
from __future__ import annotations

from dataclasses import dataclass

from bi_auth import RbacPolicy
from bi_data import QueryRunner
from bi_llm import JsonTaskRouter
from bi_schema_rag import SchemaRetriever
from bi_sql_guard import SqlGuard


@dataclass(frozen=True)
class GraphDeps:
    router: JsonTaskRouter
    retriever: SchemaRetriever
    rbac: RbacPolicy
    query_runner: QueryRunner
    sql_guard_factory: type[SqlGuard] = SqlGuard
    max_rows: int = 10000
