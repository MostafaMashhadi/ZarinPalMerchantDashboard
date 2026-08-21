from __future__ import annotations

import csv
import hashlib
import io
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from ingestion.client import ClickHouseClient
from ingestion.config import (
    ClickHouseConfig,
    PostgresConfig,
    default_clickhouse_config,
    default_postgres_config,
)
from ingestion.validator import RowValidator, ValidatedRow, ValidationError
from repositories.ingest_batch_repository import DuplicateBatchError, IngestBatchRepository

logger = logging.getLogger(__name__)


class IngestionPipelineError(Exception):
    """Exception raised when ingestion pipeline fails."""


@dataclass(frozen=True)
class IngestionResult:
    batch_id: UUID
    batch_key: str
    row_count: int
    status: str
    committed_at: datetime | None


class CSVIngestionPipeline:
    """Idempotent CSV Ingestion Pipeline per spec §5.4 / Task 1.1.

    7-step flow:
    1. Compute batch_key = sha256(file_content)
    2. Register in Postgres INGEST_BATCH with status='staging' (unique constraint is single gate)
    3. Stream and validate CSV rows (schema + status-conditional nulls + PSP prefix)
    4. Insert valid rows into ClickHouse tx_staging tagged with ingest_batch_id
    5. On success: INSERT INTO tx_raw SELECT ... FROM tx_staging WHERE ingest_batch_id = :id
    6. Mark INGEST_BATCH status='committed', row_count, committed_at = now()
    7. On failure: mark INGEST_BATCH status='failed', leave tx_raw untouched
    """

    def __init__(
        self,
        ch_client: ClickHouseClient | None = None,
        batch_repo: IngestBatchRepository | None = None,
        ch_config: ClickHouseConfig | None = None,
        pg_config: PostgresConfig | None = None,
        batch_size: int = 10000,
    ) -> None:
        self.ch_client = ch_client or ClickHouseClient(ch_config or default_clickhouse_config)
        self.batch_repo = batch_repo or IngestBatchRepository(pg_config or default_postgres_config)
        self.validator = RowValidator()
        self.batch_size = batch_size

    def compute_sha256(self, file_obj: BinaryIO | bytes | str | Path) -> tuple[str, bytes]:
        """Compute SHA256 hex digest of file contents and return (sha256, raw_bytes)."""
        hasher = hashlib.sha256()
        if isinstance(file_obj, (str, Path)):
            path = Path(file_obj)
            if not path.exists():
                raise FileNotFoundError(f"CSV file not found: {path}")
            raw_bytes = path.read_bytes()
        elif isinstance(file_obj, bytes):
            raw_bytes = file_obj
        else:
            raw_bytes = file_obj.read()

        hasher.update(raw_bytes)
        return hasher.hexdigest(), raw_bytes

    def ingest_file(
        self,
        file_source: BinaryIO | bytes | str | Path,
        dry_run: bool = False,
    ) -> IngestionResult:
        """Run the full idempotent ingestion pipeline against a CSV source."""
        # Step 1: Compute batch_key = sha256(file_content)
        batch_key, raw_bytes = self.compute_sha256(file_source)
        logger.info("Computed SHA256 batch_key: %s", batch_key)

        if dry_run:
            logger.info("DRY RUN: Validating without database writes.")
            validated_rows = self._parse_and_validate_stream(raw_bytes, UUID("00000000-0000-0000-0000-000000000000"))
            return IngestionResult(
                batch_id=UUID("00000000-0000-0000-0000-000000000000"),
                batch_key=batch_key,
                row_count=len(validated_rows),
                status="dry_run_validated",
                committed_at=None,
            )

        # Step 2: Attempt INSERT INTO INGEST_BATCH (batch_key, status='staging')
        # Unique constraint is the single gate against duplicate files
        try:
            batch_record = self.batch_repo.create_batch(batch_key=batch_key, status="staging")
        except DuplicateBatchError as e:
            logger.warning("Duplicate file detected for batch_key %s: %s", batch_key, e)
            existing = self.batch_repo.get_by_key(batch_key)
            if existing:
                return IngestionResult(
                    batch_id=existing.id,
                    batch_key=existing.batch_key,
                    row_count=existing.row_count,
                    status=existing.status,
                    committed_at=existing.committed_at,
                )
            raise

        batch_id = batch_record.id
        logger.info("Registered IngestBatch id=%s status='staging'", batch_id)

        try:
            # Step 3 & 4: Parse, validate and stream into tx_staging in batches
            validated_rows = self._parse_and_validate_stream(raw_bytes, batch_id)
            total_rows = len(validated_rows)
            logger.info("Successfully validated %d rows for batch %s", total_rows, batch_id)

            # Insert into tx_staging
            for i in range(0, total_rows, self.batch_size):
                chunk = validated_rows[i : i + self.batch_size]
                chunk_dicts = [r.to_dict() for r in chunk]
                self.ch_client.insert_json_rows("tx_staging", chunk_dicts)
                logger.info("Inserted chunk [%d..%d] into tx_staging", i, min(i + self.batch_size, total_rows))

            # Step 5: On validation & staging success, promote to tx_raw
            promote_sql = f"""
            INSERT INTO tx_raw
            SELECT
                session_key,
                try_seq,
                terminal_key,
                merchant_key,
                category_id,
                category_title,
                amount,
                adjusted_fee,
                session_status,
                try_status,
                switch_response_code,
                psp_code,
                issuer_bank_code,
                payer_card_key,
                verify_type,
                init_time_ms,
                verify_time_ms,
                created_at,
                try_created_at,
                verified_at,
                settled_at,
                expire_in,
                ingest_batch_id
            FROM tx_staging
            WHERE ingest_batch_id = '{batch_id}'
            """
            self.ch_client.execute_statement(promote_sql)
            logger.info("Promoted %d rows from tx_staging to tx_raw for batch %s", total_rows, batch_id)

            # Step 6: Mark INGEST_BATCH status='committed'
            committed_time = datetime.now(UTC)
            self.batch_repo.update_status(
                batch_id=batch_id,
                status="committed",
                row_count=total_rows,
                committed_at=committed_time,
            )
            logger.info("IngestBatch %s marked 'committed' with %d rows", batch_id, total_rows)

            return IngestionResult(
                batch_id=batch_id,
                batch_key=batch_key,
                row_count=total_rows,
                status="committed",
                committed_at=committed_time,
            )

        except Exception as e:
            # Step 7: On any failure, mark status='failed', leave tx_raw untouched
            logger.error("Ingestion failed for batch %s: %s. Marking status='failed'", batch_id, e)
            try:
                self.batch_repo.update_status(batch_id=batch_id, status="failed", row_count=0)
            except Exception as update_err:
                logger.error("Failed to update batch status to 'failed': %s", update_err)
            raise IngestionPipelineError(f"Ingestion failed for batch {batch_id}: {e}") from e

    def _parse_and_validate_stream(self, raw_bytes: bytes, batch_id: UUID) -> list[ValidatedRow]:
        """Parse raw CSV bytes and validate each row."""
        text_stream = io.StringIO(raw_bytes.decode("utf-8-sig", errors="replace"))
        reader = csv.DictReader(text_stream)
        validated: list[ValidatedRow] = []

        for idx, row in enumerate(reader, start=1):
            try:
                val_row = self.validator.validate_row(row, batch_id, row_index=idx)
                validated.append(val_row)
            except ValidationError as e:
                raise IngestionPipelineError(f"Validation failed at row {idx}: {e}") from e

        return validated
