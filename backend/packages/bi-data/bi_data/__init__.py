"""bi-data — read-only data access + audit persistence.

    from bi_data import QueryRunner, Dataset, AuditLogWriter, AuditEntry

    runner = QueryRunner.from_url("mysql+pymysql://user:pw@host/ENTERPRISE_BI")
    ds = runner.execute("SELECT BRANCH_NAME, SUM(COLLECTION_AMOUNT) ... LIMIT 100")
    ds.column_types()   # {'BRANCH_NAME': 'categorical', ...}

Analytical queries run inside an always-rolled-back read-only transaction; the
audit writer commits to AUDIT_LOG on its own connection.
"""
from __future__ import annotations

from bi_data.audit import AuditEntry, AuditLogWriter
from bi_data.dataset import Dataset
from bi_data.engine import QueryRunner

__version__ = "0.1.0"

__all__ = [
    "QueryRunner",
    "Dataset",
    "AuditLogWriter",
    "AuditEntry",
    "__version__",
]
