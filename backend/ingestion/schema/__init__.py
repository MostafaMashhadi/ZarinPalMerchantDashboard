"""Schema and migrations package for ClickHouse."""

from .migrate import apply_clickhouse_schema

__all__ = ["apply_clickhouse_schema"]
