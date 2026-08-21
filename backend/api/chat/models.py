"""Conversational chat models (§5.3, §9.6, §19.25)."""

from __future__ import annotations

import uuid

from django.db import models

from merchants.models import Merchant, MerchantUser


class ChatSession(models.Model):
    """A chat session for a merchant user (§19.25).

    Maps to CHAT_SESSION table. Each session is scoped to a single
    merchant and a single merchant_user (the authenticated portal user).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        db_column="merchant_id",
    )
    merchant_user = models.ForeignKey(
        MerchantUser,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        db_column="merchant_user_id",
    )
    status = models.CharField(max_length=32)
    language_hint = models.CharField(max_length=16, default="fa")
    started_at = models.DateTimeField()
    last_activity_at = models.DateTimeField()

    class Meta:
        db_table = "chat_session"
        indexes = [
            models.Index(
                fields=["merchant", "last_activity_at"],
                name="cs_mer_last_act_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Session {self.id} ({self.status})"


class ChatMessage(models.Model):
    """A single chat message within a session (§19.25).

    Maps to CHAT_MESSAGE table. role is 'user' or 'assistant'.
    referenced_insight_ids ties assistant messages to the insights
    (and underlying ClickHouse queries) that grounded their content (§9.6.4).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        db_column="session_id",
    )
    role = models.CharField(max_length=32)
    content = models.TextField()
    referenced_insight_ids = models.JSONField(default=list)
    tokens_in = models.IntegerField(default=0)
    tokens_out = models.IntegerField(default=0)
    model_used = models.CharField(max_length=128, blank=True)
    delivery_mode = models.CharField(max_length=32, default="buffered")
    created_at = models.DateTimeField()

    class Meta:
        db_table = "chat_message"
        indexes = [
            models.Index(
                fields=["session", "created_at"],
                name="cm_session_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.role} msg in session {self.session_id}"


class ChatTurnStep(models.Model):
    """A persisted step within a chat turn (§19.25, §19.27).

    Maps to CHAT_TURN_STEP table. Mirrors AGENT_RUN_STEP's shape
    deliberately — same durability philosophy (Memento/Checkpoint, §6),
    lighter weight (no Temporal workflow per row).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name="turn_steps",
        db_column="message_id",
    )
    step_name = models.CharField(max_length=128)
    status = models.CharField(max_length=32)
    checkpoint_state = models.JSONField(default=dict)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6)
    executed_at = models.DateTimeField()

    class Meta:
        db_table = "chat_turn_step"
        indexes = [
            models.Index(
                fields=["message"],
                name="cts_message_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.message_id}::{self.step_name} ({self.status})"


class MerchantChatMemory(models.Model):
    """Consolidated chat memory per merchant for a billing period (§19.19).

    Maps to MERCHANT_CHAT_MEMORY table. Stores periodic memory consolidation
    output used to preserve context across chat sessions without storing
    every raw message indefinitely.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="chat_memories",
        db_column="merchant_id",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    summary_text = models.TextField()
    key_facts = models.JSONField(default=list)
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "merchant_chat_memory"
        indexes = [
            models.Index(
                fields=["merchant", "period_start"],
                name="mcm_mer_period_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Memory for {self.merchant_id} [{self.period_start}-{self.period_end}]"


__all__ = [
    "ChatMessage",
    "ChatSession",
    "ChatTurnStep",
    "MerchantChatMemory",
]
