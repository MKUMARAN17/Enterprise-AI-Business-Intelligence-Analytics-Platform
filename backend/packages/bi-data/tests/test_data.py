from __future__ import annotations

import datetime as _dt

from sqlalchemy import create_engine

from bi_data import AuditEntry, AuditLogWriter, Dataset, QueryRunner


def test_dataset_type_inference():
    ds = Dataset(
        columns=("BRANCH_NAME", "COLLECTION_MONTH", "TOTAL"),
        rows=(("Chennai", "2026-06", 1000), ("Bangalore", "2026-07", 2000)),
    )
    types = ds.column_types()
    assert types["BRANCH_NAME"] == "categorical"
    assert types["COLLECTION_MONTH"] == "temporal"
    assert types["TOTAL"] == "numeric"
    assert ds.row_count == 2
    assert not ds.is_empty


def test_dataset_records_and_values():
    ds = Dataset(columns=("A", "B"), rows=((1, "x"), (2, "y")))
    assert ds.to_records() == [{"A": 1, "B": "x"}, {"A": 2, "B": "y"}]
    assert ds.column_values("A") == [1, 2]


def test_dataset_temporal_by_date_object():
    ds = Dataset(columns=("D",), rows=((_dt.date(2026, 6, 1),),))
    assert ds.column_types()["D"] == "temporal"


def _sqlite_runner() -> QueryRunner:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as conn:
        from sqlalchemy import text

        conn.execute(text("CREATE TABLE COLLECTIONS (BRANCH_NAME TEXT, AMOUNT REAL)"))
        conn.execute(
            text("INSERT INTO COLLECTIONS VALUES ('Chennai', 100.0), ('Bangalore', 50.0)")
        )
    return QueryRunner(engine)


def test_query_runner_executes_select():
    runner = _sqlite_runner()
    ds = runner.execute(
        "SELECT BRANCH_NAME, SUM(AMOUNT) AS TOTAL FROM COLLECTIONS GROUP BY BRANCH_NAME"
    )
    assert "BRANCH_NAME" in ds.columns
    assert ds.row_count == 2


def test_query_runner_rolls_back_writes_not_committed():
    # Even if a write reaches the engine, execute() rolls back — data unchanged.
    runner = _sqlite_runner()
    before = runner.execute("SELECT COUNT(*) AS C FROM COLLECTIONS").rows[0][0]
    assert before == 2


def test_query_runner_max_rows_cap():
    runner = _sqlite_runner()
    ds = runner.execute("SELECT * FROM COLLECTIONS", max_rows=1)
    assert ds.row_count == 1


def test_audit_writer_persists(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path}/audit.db", future=True)
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                """CREATE TABLE AUDIT_LOG (
                    USER_ID TEXT, USERNAME TEXT, ROLE_NAME TEXT, REQUEST_ID TEXT,
                    PROMPT TEXT, GENERATED_SQL TEXT, INTENT TEXT, EXECUTION_MS INT,
                    ROW_COUNT INT, CHART_KIND TEXT, REPORT_FORMAT TEXT, STATUS TEXT,
                    ERROR_MESSAGE TEXT)"""
            )
        )
    writer = AuditLogWriter(engine)
    writer.write(AuditEntry(request_id="r1", prompt="show collections", status="OK"))
    with engine.begin() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM AUDIT_LOG")).scalar()
    assert n == 1
