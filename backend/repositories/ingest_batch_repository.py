from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from ingestion.config import PostgresConfig, default_postgres_config

logger = logging.getLogger(__name__)


class IngestBatchError(Exception):
    """Base exception for IngestBatch operations."""


class DuplicateBatchError(IngestBatchError):
    """Raised when a batch with the same batch_key (SHA256) already exists."""


@dataclass(frozen=True)
class IngestBatchRecord:
    id: UUID
    batch_key: str
    status: str
    row_count: int
    committed_at: datetime | None


class IngestBatchRepository:
    """PostgreSQL repository for INGEST_BATCH table.

    Works via Django ORM when Django apps are loaded, or via direct psycopg connection.
    """

    def __init__(self, config: PostgresConfig | None = None) -> None:
        self.config = config or default_postgres_config

    def _get_django_model(self) -> Any:
        try:
            from analytics.models import IngestBatch

            return IngestBatch
        except Exception:
            return None

    def create_batch(self, batch_key: str, status: str = "staging") -> IngestBatchRecord:
        """Create a new batch record in 'staging' status. Fails on duplicate batch_key."""
        model = self._get_django_model()
        if model is not None:
            try:
                from django.db import IntegrityError

                rec = model.objects.create(
                    id=uuid.uuid4(),
                    batch_key=batch_key,
                    status=status,
                    row_count=0,
                )
                return IngestBatchRecord(
                    id=rec.id,
                    batch_key=rec.batch_key,
                    status=rec.status,
                    row_count=rec.row_count,
                    committed_at=rec.committed_at,
                )
            except IntegrityError as e:
                raise DuplicateBatchError(f"Duplicate batch with key {batch_key}") from e
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    raise DuplicateBatchError(f"Duplicate batch with key {batch_key}") from e
                raise IngestBatchError(f"Failed to create IngestBatch: {e}") from e

        # Fallback to psycopg direct connection
        import psycopg

        batch_id = uuid.uuid4()
        try:
            with psycopg.connect(self.config.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ingest_batch (id, batch_key, status, row_count, committed_at)
                        VALUES (%s, %s, %s, 0, NULL)
                        RETURNING id, batch_key, status, row_count, committed_at
                        """,
                        (batch_id, batch_key, status),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row is None:
                        raise IngestBatchError("Failed to insert IngestBatch row")
                    return IngestBatchRecord(
                        id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                        batch_key=row[1],
                        status=row[2],
                        row_count=row[3],
                        committed_at=row[4],
                    )
        except psycopg.errors.UniqueViolation as e:
            raise DuplicateBatchError(f"Duplicate batch with key {batch_key}") from e
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                raise DuplicateBatchError(f"Duplicate batch with key {batch_key}") from e
            raise IngestBatchError(f"Direct DB IngestBatch insert error: {e}") from e

    def get_by_key(self, batch_key: str) -> IngestBatchRecord | None:
        """Find an IngestBatch by its unique sha256 batch_key."""
        model = self._get_django_model()
        if model is not None:
            try:
                rec = model.objects.filter(batch_key=batch_key).first()
                if not rec:
                    return None
                return IngestBatchRecord(
                    id=rec.id,
                    batch_key=rec.batch_key,
                    status=rec.status,
                    row_count=rec.row_count,
                    committed_at=rec.committed_at,
                )
            except Exception as e:
                logger.warning("Django ORM lookup failed: %s", e)

        import psycopg

        try:
            with psycopg.connect(self.config.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, batch_key, status, row_count, committed_at FROM ingest_batch WHERE batch_key = %s",
                        (batch_key,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return IngestBatchRecord(
                        id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                        batch_key=row[1],
                        status=row[2],
                        row_count=row[3],
                        committed_at=row[4],
                    )
        except Exception as e:
            logger.warning("Direct DB lookup error: %s", e)
            return None

    def get_by_id(self, batch_id: UUID) -> IngestBatchRecord | None:
        """Find an IngestBatch by UUID."""
        model = self._get_django_model()
        if model is not None:
            try:
                rec = model.objects.filter(id=batch_id).first()
                if not rec:
                    return None
                return IngestBatchRecord(
                    id=rec.id,
                    batch_key=rec.batch_key,
                    status=rec.status,
                    row_count=rec.row_count,
                    committed_at=rec.committed_at,
                )
            except Exception as e:
                logger.warning("Django ORM lookup failed: %s", e)

        import psycopg

        try:
            with psycopg.connect(self.config.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, batch_key, status, row_count, committed_at FROM ingest_batch WHERE id = %s",
                        (batch_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    return IngestBatchRecord(
                        id=row[0] if isinstance(row[0], UUID) else UUID(str(row[0])),
                        batch_key=row[1],
                        status=row[2],
                        row_count=row[3],
                        committed_at=row[4],
                    )
        except Exception as e:
            logger.warning("Direct DB lookup error: %s", e)
            return None

    def update_status(
        self,
        batch_id: UUID,
        status: str,
        row_count: int = 0,
        committed_at: datetime | None = None,
    ) -> None:
        """Update batch status, row count, and committed timestamp."""
        if status == "committed" and committed_at is None:
            committed_at = datetime.now(UTC)

        model = self._get_django_model()
        if model is not None:
            try:
                model.objects.filter(id=batch_id).update(
                    status=status,
                    row_count=row_count,
                    committed_at=committed_at,
                )
                return
            except Exception as e:
                logger.warning("Django ORM update failed: %s", e)

        import psycopg

        try:
            with psycopg.connect(self.config.dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE ingest_batch
                        SET status = %s, row_count = %s, committed_at = %s
                        WHERE id = %s
                        """,
                        (status, row_count, committed_at, batch_id),
                    )
                    conn.commit()
        except Exception as e:
            raise IngestBatchError(f"Direct DB IngestBatch update error: {e}") from e
