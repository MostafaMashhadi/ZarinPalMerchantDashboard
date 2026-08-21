"""Agentic models (§5.3, §9.1, §19.16)."""

from __future__ import annotations

import uuid

from django.db import models

from merchants.models import Merchant


class AgentRun(models.Model):
    """An agentic insight-generation run (§19.16).

    Maps to AGENT_RUN table. workflow_id is unique — one active run
    per workflow at any time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="agent_runs",
        db_column="merchant_id",
    )
    workflow_id = models.CharField(max_length=128, unique=True)
    status = models.CharField(max_length=32)
    checkpoint_state = models.JSONField(default=dict)
    tokens_used = models.IntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=6)
    cost_ceiling_usd = models.DecimalField(max_digits=12, decimal_places=6)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_run"

    def __str__(self) -> str:
        return f"{self.workflow_id} ({self.status})"


class AgentRunStep(models.Model):
    """A single step within an AGENT_RUN, mirroring CHAT_TURN_STEP's shape (§6.3, §19.17).

    Maps to AGENT_RUN_STEP table. Each step records the Chain-of-Responsibility
    hop, model used, token counts, and cost for audit/traceability.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="steps",
        db_column="agent_run_id",
    )
    step_name = models.CharField(max_length=128)
    status = models.CharField(max_length=32)
    input_snapshot = models.JSONField(default=dict)
    output_snapshot = models.JSONField(default=dict)
    model_used = models.CharField(max_length=128)
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6)
    executed_at = models.DateTimeField()

    class Meta:
        db_table = "agent_run_step"
        indexes = [
            models.Index(
                fields=["agent_run", "executed_at"],
                name="ars_run_ts_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.agent_run_id}::{self.step_name} ({self.status})"


class IdempotencyKey(models.Model):
    """Idempotency key registry for safe retries (§19.13, §19.15).

    Maps to IDEMPOTENCY_KEY table. scope partitions keys so the same
    key string can be used across different endpoint families without
    collision (e.g. "insight_generation" vs "notification_dispatch").
    """

    key = models.CharField(max_length=128, primary_key=True)
    scope = models.CharField(max_length=64)
    response_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "idempotency_key"
        indexes = [
            models.Index(
                fields=["scope", "expires_at"],
                name="idem_scope_exp_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scope}:{self.key}"


__all__ = [
    "AgentRun",
    "AgentRunStep",
    "IdempotencyKey",
]
