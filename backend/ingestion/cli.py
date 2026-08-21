from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from ingestion.client import ClickHouseClient  # noqa: E402
from ingestion.pipeline import CSVIngestionPipeline, IngestionPipelineError  # noqa: E402
from ingestion.schema.migrate import apply_clickhouse_schema  # noqa: E402
from repositories.ingest_batch_repository import DuplicateBatchError  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion.cli")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ZarinPal CSV Ingestion Pipeline CLI (Pourya, Sprint 1)",
    )
    parser.add_argument("csv_file", nargs="?", help="Path to transaction CSV file to ingest")
    parser.add_argument("--dry-run", action="store_true", help="Validate CSV without database writes")
    parser.add_argument("--apply-schema", action="store_true", help="Apply ClickHouse DDL schema before ingesting")
    parser.add_argument("--ping", action="store_true", help="Check ClickHouse server connectivity")

    args = parser.parse_args()

    ch_client = ClickHouseClient()

    if args.ping:
        ok = ch_client.ping()
        if ok:
            print("ClickHouse is REACHABLE (OK)")
            return 0
        else:
            print("ClickHouse ping FAILED", file=sys.stderr)
            return 1

    if args.apply_schema:
        print("Applying ClickHouse DDL schema...")
        applied = apply_clickhouse_schema(client=ch_client)
        print(f"Successfully applied {len(applied)} statements.")
        if not args.csv_file:
            return 0

    if not args.csv_file:
        parser.print_help()
        return 1

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}", file=sys.stderr)
        return 1

    pipeline = CSVIngestionPipeline(ch_client=ch_client)

    try:
        print(f"Starting ingestion of {csv_path} (dry_run={args.dry_run})...")
        result = pipeline.ingest_file(csv_path, dry_run=args.dry_run)
        print("Ingestion SUCCEEDED:")
        print(f"  Batch ID:     {result.batch_id}")
        print(f"  Batch Key:    {result.batch_key}")
        print(f"  Row Count:    {result.row_count}")
        print(f"  Status:       {result.status}")
        print(f"  Committed At: {result.committed_at}")
        return 0
    except DuplicateBatchError as e:
        print(f"Duplicate Batch (Rejected): {e}", file=sys.stderr)
        return 0  # Idempotent success
    except IngestionPipelineError as e:
        print(f"Ingestion FAILED: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error during ingestion: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
