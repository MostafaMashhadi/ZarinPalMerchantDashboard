from pathlib import Path

from ingestion.schema.migrate import parse_sql_statements


def test_clickhouse_ddl_file_exists() -> None:
    ddl_path = Path(__file__).resolve().parent.parent / "ingestion" / "schema" / "clickhouse.sql"
    assert ddl_path.exists(), "clickhouse.sql must exist in backend/ingestion/schema/"


def test_clickhouse_ddl_tables_and_views_present() -> None:
    ddl_path = Path(__file__).resolve().parent.parent / "ingestion" / "schema" / "clickhouse.sql"
    sql = ddl_path.read_text(encoding="utf-8")
    statements = parse_sql_statements(sql)

    assert len(statements) == 5, f"Expected 5 DDL statements, found {len(statements)}"

    table_names = ["tx_staging", "tx_raw", "tx_daily_rollup", "category_daily_rollup", "terminal_noattempt_clusters"]
    for table_name in table_names:
        assert any(table_name in stmt for stmt in statements), f"Missing DDL for {table_name}"


def test_clickhouse_ddl_corrected_column_names() -> None:
    """Validate §5.4 corrected column name: expire_in, NOT expire_at."""
    ddl_path = Path(__file__).resolve().parent.parent / "ingestion" / "schema" / "clickhouse.sql"
    sql = ddl_path.read_text(encoding="utf-8")

    assert "expire_in" in sql, "expire_in column must be present in ClickHouse DDL"
    assert "expire_at" not in sql, "expire_at column must NOT be used (renamed to expire_in per §5.4)"
    assert "try_created_at        Nullable(DateTime)" in sql or "try_created_at" in sql


def test_clickhouse_ddl_codecs_and_aggregates() -> None:
    """Validate Delta+ZSTD codecs in tx_raw and sessions_reversed_state in rollups."""
    ddl_path = Path(__file__).resolve().parent.parent / "ingestion" / "schema" / "clickhouse.sql"
    sql = ddl_path.read_text(encoding="utf-8")

    # Codecs on fact table
    assert "CODEC(Delta, ZSTD(3))" in sql

    # Reversals tracked in daily rollup
    assert "sessions_reversed_state" in sql
    assert "uniqExactIfState(session_key, session_status = 'Reversed')" in sql

    # Anomaly clusters filter
    assert "WHERE try_status = 'NoAttempt'" in sql
    assert "round(amount, -4)" in sql
