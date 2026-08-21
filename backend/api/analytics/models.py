"""Analytics app models (§5.3, §5.4, §7).

Contains ingestion, insight, agentic, and chat cost-ledger models.
"""

from __future__ import annotations

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


class Notification(models.Model):
    """Notification row for in-app notification bell (§9.5).

    Maps to NOTIFICATION table. References an Insight that triggered
    the notification. severity determines badge color in the UI.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="merchant_id",
    )
    insight = models.ForeignKey(
        Insight,
        on_delete=models.PROTECT,
        related_name="notifications",
        db_column="insight_id",
    )
    channel = models.CharField(max_length=32)
    status = models.CharField(max_length=32)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification"
        indexes = [
            models.Index(
                fields=["merchant", "status", "created_at"],
                name="notif_mer_st_cr_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Notification {self.id} ({self.status})"


class CostLedgerEntry(models.Model):
    """Per-step cost ledger entry shared by agent and chat scopes (§6.5, §9.3).

    Maps to COST_LEDGER_ENTRY table. Exactly one of
    agent_run_step_id / chat_turn_step_id is populated per row,
    enforced by a database CHECK constraint (not just application code).

    The daily-sum queries the Singleton CostLedger issues use the
    (scope, merchant_id, ledger_date) composite index.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_run_step = models.ForeignKey(
        "agent.AgentRunStep",
        on_delete=models.CASCADE,
        related_name="cost_ledger_entries",
        db_column="agent_run_step_id",
        null=True,
        blank=True,
    )
    chat_turn_step = models.ForeignKey(
        "chat.ChatTurnStep",
        on_delete=models.CASCADE,
        related_name="cost_ledger_entries",
        db_column="chat_turn_step_id",
        null=True,
        blank=True,
    )
    scope = models.CharField(max_length=32)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="cost_ledger_entries",
        db_column="merchant_id",
    )
    amount_usd = models.DecimalField(max_digits=12, decimal_places=6)
    ledger_date = models.DateField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = "cost_ledger_entry"
        indexes = [
            models.Index(
                fields=["scope", "merchant", "ledger_date"],
                name="cle_scope_merchant_date_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(agent_run_step__isnull=True, chat_turn_step__isnull=False)
                    | models.Q(agent_run_step__isnull=False, chat_turn_step__isnull=True)
                ),
                name="cle_one_fkey_chk",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(scope="agent") & models.Q(agent_run_step__isnull=False)
                    | models.Q(scope="chat") & models.Q(chat_turn_step__isnull=False)
                ),
                name="cle_scope_fkey_chk",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scope} cost {self.amount_usd} on {self.ledger_date}"


__all__ = [
    "CostLedgerEntry",
    "IngestBatch",
    "Insight",
    "InsightAction",
    "InsightProvenance",
    "Notification",
]
