from pathlib import Path


def test_staging_7_day_ttl_policy() -> None:
    ddl_path = Path(__file__).resolve().parent.parent / "ingestion" / "schema" / "clickhouse.sql"
    sql = ddl_path.read_text(encoding="utf-8")

    assert "tx_staging" in sql
    assert "TTL created_at + INTERVAL 7 DAY" in sql


def test_raw_24_month_retention_policy() -> None:
    retention_path = Path(__file__).resolve().parent.parent / "ingestion" / "schema" / "retention.sql"
    assert retention_path.exists()
    sql = retention_path.read_text(encoding="utf-8")

    assert "tx_raw" in sql
    assert "INTERVAL 24 MONTH" in sql
