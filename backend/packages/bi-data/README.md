# bi-data

Read-only query execution + audit persistence against `ENTERPRISE_BI`.

```python
from bi_data import QueryRunner, AuditLogWriter, AuditEntry

runner = QueryRunner.from_url("mysql+pymysql://user:pw@localhost/ENTERPRISE_BI")
ds = runner.execute("SELECT BRANCH_NAME, SUM(COLLECTION_AMOUNT) AS TOTAL FROM COLLECTIONS GROUP BY BRANCH_NAME LIMIT 100")
ds.row_count, ds.columns, ds.column_types()
```

- Analytical queries run inside an **always-rolled-back** transaction (never committed) + a hard `fetchmany` row cap → defence in depth behind the SQL guard.
- `Dataset` is the immutable hand-off shape (UPPERCASE columns) consumed by `bi-viz`, `bi-reports`, and the insight agent.
- `AuditLogWriter` commits one `AUDIT_LOG` row per turn and never raises into the request path.
- MySQL driver is the optional `[mysql]` extra (`pymysql`); tests use in-memory SQLite.
