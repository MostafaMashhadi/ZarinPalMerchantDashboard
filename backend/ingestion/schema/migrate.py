from __future__ import annotations

import logging
import re
from pathlib import Path

from ingestion.client import ClickHouseClient
from ingestion.config import ClickHouseConfig

logger = logging.getLogger(__name__)


def parse_sql_statements(sql_text: str) -> list[str]:
    """Split SQL file contents into executable statements while preserving multi-line blocks."""
    # Remove single line comments
    lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    clean_text = "\n".join(lines)

    # Split by semicolon followed by whitespace/newline
    raw_statements = [s.strip() for s in re.split(r";(?:\s*\n|\s*$)", clean_text) if s.strip()]
    return raw_statements


def apply_clickhouse_schema(
    client: ClickHouseClient | None = None,
    config: ClickHouseConfig | None = None,
) -> list[str]:
    """Apply ClickHouse DDL schema definitions idempotently."""
    cli = client or ClickHouseClient(config)
    schema_dir = Path(__file__).resolve().parent
    ddl_file = schema_dir / "clickhouse.sql"

    if not ddl_file.exists():
        raise FileNotFoundError(f"Schema file not found at {ddl_file}")

    with open(ddl_file, encoding="utf-8") as f:
        sql_content = f.read()

    statements = parse_sql_statements(sql_content)
    applied: list[str] = []

    for stmt in statements:
        logger.info("Applying ClickHouse DDL statement:\n%s", stmt[:100])
        cli.execute_statement(stmt)
        # Extract table/view name for reporting
        first_line = stmt.split("\n")[0]
        applied.append(first_line)

    logger.info("Successfully applied %d ClickHouse DDL statements.", len(applied))
    return applied


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply_clickhouse_schema()
