import uuid

from django.db import models

from merchants.models import Merchant


class IngestBatch(models.Model):
    """Batch registry owned by the ingestion pipeline (Pourya, §5.4)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_key = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=32)
    row_count = models.IntegerField(default=0)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ingest_batch"

    def __str__(self) -> str:
        return self.batch_key


class Insight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="insights",
        db_column="merchant_id",
    )
    kind = models.CharField(max_length=64)
    headline = models.CharField(max_length=512)
    body = models.JSONField(default=dict)
    status = models.CharField(max_length=32)
    low_confidence_peer_set = models.BooleanField(default=False)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    generated_at = models.DateTimeField()
    # AGENT_RUN lands in Sprint 3; store UUID without FK until that model exists.
    agent_run_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "insight"
        indexes = [
            models.Index(
                fields=["merchant", "period_start", "period_end", "kind"],
                name="insight_merchant_period_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind}: {self.headline[:50]}"


class InsightProvenance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insight = models.ForeignKey(
        Insight,
        on_delete=models.CASCADE,
        related_name="provenance_records",
        db_column="insight_id",
    )
    sequence = models.IntegerField()
    source_query_id = models.CharField(max_length=128)
    clickhouse_sql = models.TextField()
    query_params = models.JSONField(default=dict)
    ingest_batch = models.ForeignKey(
        IngestBatch,
        on_delete=models.PROTECT,
        related_name="provenance_records",
        db_column="ingest_batch_id",
    )
    computed_at = models.DateTimeField()
    result_summary = models.JSONField(default=dict)

    class Meta:
        db_table = "insight_provenance"
        indexes = [
            models.Index(
                fields=["insight", "sequence"],
                name="insight_provenance_seq_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.insight_id}#{self.sequence}"


class InsightAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    insight = models.ForeignKey(
        Insight,
        on_delete=models.CASCADE,
        related_name="actions",
        db_column="insight_id",
    )
    action_text = models.TextField()
    priority = models.CharField(max_length=32)
    sort_order = models.IntegerField()

    class Meta:
        db_table = "insight_action"

    def __str__(self) -> str:
        return self.action_text[:50]
