# bi-sql-guard

Fail-closed validation of **LLM-generated SQL** before it ever reaches the
database. This is the security boundary for a natural-language-to-SQL BI
platform: the model's output is untrusted, so every query is statically checked
and rejected unless it is provably safe.

## What it enforces

1. Comments (`-- ...`, `/* ... */`) are stripped **before** analysis so payloads
   cannot hide inside them.
2. Empty / whitespace-only input is rejected.
3. Exactly one statement is allowed (a single trailing `;` is fine); stacked
   statements are rejected.
4. Only `SELECT` and `WITH ... SELECT` (CTE) queries are permitted. Any
   DDL/DML leading keyword (INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/…)
   is rejected.
5. The whole token stream is scanned for destructive/exfiltration constructs
   (`INTO OUTFILE`, `INTO DUMPFILE`, `LOAD_FILE(`, `SLEEP(`, `BENCHMARK(`, and
   bare destructive keywords) as defence in depth.
6. Referenced tables are extracted and checked against a per-role allow-list.
7. A safety `LIMIT` is appended when the query has none.

## Usage

```python
from bi_sql_guard import SqlGuard

guard = SqlGuard(allowed_tables={"ORDERS", "CUSTOMERS"}, max_limit=1000)

# Raising API (recommended on the execution path) — fail closed.
result = guard.validate("SELECT * FROM orders")
assert result.ok
run(result.normalized_sql)   # "SELECT * FROM orders LIMIT 1000"

# Non-raising API — returns a result object instead.
result = guard.try_validate("DROP TABLE orders")
assert not result.ok
print(result.reason)
```

`allowed_tables=None` (the default) skips per-role table scoping but still blocks
all DDL/DML and dangerous constructs.

## Limitations

Table extraction is regex-based (no external SQL parser) and does not resolve
subqueries / derived tables / table-valued functions to base tables. Because
authorization is an allow-list check, any unrecognised name fails closed. Do not
treat this guard as a substitute for least-privilege database credentials — it
is one layer of defence in depth.
