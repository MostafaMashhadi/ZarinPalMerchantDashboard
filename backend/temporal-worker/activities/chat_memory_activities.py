"""Activities for ChatMemoryConsolidationWorkflow (§9.6.3, §19.28).

Activity sequence:
1. FindSessionsToConsolidate — find sessions with messages past the 30-day cutoff
2. SummarizeChatMemory — summarize aging messages via ModelRouterChain (scope="chat")
3. UpsertMerchantChatMemory — additive/merge upsert into MERCHANT_CHAT_MEMORY
4. DeleteConsolidatedMessages — delete the now-consolidated CHAT_MESSAGE rows

Deletion strictly follows successful upsert; Temporal durable execution
guarantees resume from the last completed activity (§19.19, §19.28).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from gateway.chain import build_default_chain
from gateway.cost_ledger import CostLedger
from temporalio import activity

from shared.dtos import DraftRequest

logger = logging.getLogger(__name__)

CONSOLIDATION_AGE_DAYS = 30


@dataclass
class FindSessionsInput:
    cutoff_days: int = CONSOLIDATION_AGE_DAYS


@dataclass
class SessionInfo:
    session_id: str
    merchant_id: str
    period_start: str
    period_end: str
    message_count: int


@dataclass
class FindSessionsOutput:
    sessions: list[SessionInfo] = field(default_factory=list)


@dataclass
class SummarizeInput:
    merchant_id: str
    session_id: str
    period_start: str
    period_end: str
    messages: list[dict[str, Any]]


@dataclass
class SummarizeOutput:
    summary_text: str
    key_facts: list[str]
    tokens_in: int
    tokens_out: int
    model: str
    tier: str


@dataclass
class UpsertInput:
    merchant_id: str
    period_start: str
    period_end: str
    summary_text: str
    key_facts: list[str]
    tokens_in: int
    tokens_out: int
    model: str
    tier: str


@dataclass
class UpsertOutput:
    upserted: bool
    message: str = ""


@dataclass
class DeleteInput:
    session_id: str
    period_start: str
    period_end: str


@dataclass
class DeleteOutput:
    deleted_count: int


@activity.defn(name="FindSessionsToConsolidate")
async def find_sessions_to_consolidate(input: FindSessionsInput) -> FindSessionsOutput:
    """Find sessions with messages older than the 30-day cutoff (§19.28, step 1).

    Returns per-(merchant_id, period) groups of sessions needing consolidation.
    """
    from chat.models import ChatMessage

    cutoff = datetime.now() - timedelta(days=input.cutoff_days)

    sessions_to_consolidate: list[SessionInfo] = []

    try:
        from django.db.models import Count

        old_sessions = (
            ChatMessage.objects
            .filter(created_at__lt=cutoff)
            .values("session__merchant_id", "session_id")
            .annotate(message_count=Count("id"))
            .distinct()
        )

        for record in old_sessions:
            session_id = record["session_id"]
            merchant_id = record["session__merchant_id"]

            period_end = cutoff.replace(day=1)
            period_start = (
                period_end - timedelta(days=1)
            ).replace(day=1)

            sessions_to_consolidate.append(
                SessionInfo(
                    session_id=str(session_id),
                    merchant_id=str(merchant_id),
                    period_start=period_start.isoformat(),
                    period_end=period_end.isoformat(),
                    message_count=record["message_count"],
                )
            )
    except Exception as exc:
        logger.error("Failed to find sessions to consolidate: %s", exc)

    return FindSessionsOutput(sessions=sessions_to_consolidate)


@activity.defn(name="SummarizeChatMemory")
async def summarize_chat_memory(input: SummarizeInput) -> SummarizeOutput:
    """Summarize aging messages via ModelRouterChain (scope='chat', cheap tier) (§19.28, step 2).

    Uses the same ModelRouterChain as live chat turns, but with a summary
    system prompt. Only the cheap tier is used for consolidation.
    """
    messages_text = "\n".join(
        f"{m.get('role', 'unknown')}: {m.get('content', '')}"
        for m in input.messages[:100]
    )

    system_prompt = (
        "Summarize the following chat messages into a brief summary and "
        "extract 3-5 key facts. Return JSON with fields: summary_text, key_facts. "
        "Be concise. Approximate values are acceptable for memory purposes."
    )

    request = DraftRequest(
        scope="chat",
        estimated_tokens=2000,
        system_prompt=system_prompt,
        context={
            "tier": "cheap",
            "merchant_id": input.merchant_id,
            "session_id": input.session_id,
            "messages": messages_text,
            "period_start": input.period_start,
            "period_end": input.period_end,
        },
        stream=False,
    )

    chain = build_default_chain()
    ledger = CostLedger.instance()

    try:
        response = chain.handle(request, ledger, scope="chat")
        return SummarizeOutput(
            summary_text=response.narrative,
            key_facts=[],
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            model=response.model,
            tier=response.tier,
        )
    except Exception as exc:
        logger.error("Failed to summarize chat memory: %s", exc)
        return SummarizeOutput(
            summary_text="",
            key_facts=[],
            tokens_in=0,
            tokens_out=0,
            model="fallback",
            tier="cheap",
        )


@activity.defn(name="UpsertMerchantChatMemory")
async def upsert_merchant_chat_memory(input: UpsertInput) -> UpsertOutput:
    """Upsert into MERCHANT_CHAT_MEMORY with additive/merge semantics (§19.28, step 3).

    NEVER destructive overwrite — if a row already exists for the same
    (merchant_id, period_start, period_end), append the new summary and facts.
    """

    from chat.models import MerchantChatMemory

    period_start_dt = datetime.fromisoformat(input.period_start)
    period_end_dt = datetime.fromisoformat(input.period_end)

    try:
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            existing = MerchantChatMemory.objects.filter(
                merchant_id=input.merchant_id,
                period_start=period_start_dt,
                period_end=period_end_dt,
            ).first()

            if existing:
                existing.summary_text = (
                    (existing.summary_text or "")
                    + "\n---\n"
                    + (input.summary_text or "")
                )
                existing.key_facts = list(
                    dict.fromkeys(
                        (existing.key_facts or []) + (input.key_facts or [])
                    )
                )
                existing.updated_at = timezone.now()
                existing.save(update_fields=["summary_text", "key_facts", "updated_at"])
            else:
                MerchantChatMemory.objects.create(
                    id=uuid4_safe(),
                    merchant_id=input.merchant_id,
                    period_start=period_start_dt.date(),
                    period_end=period_end_dt.date(),
                    summary_text=input.summary_text or "",
                    key_facts=input.key_facts or [],
                    updated_at=timezone.now(),
                )
    except Exception as exc:
        logger.error("Failed to upsert merchant chat memory: %s", exc)
        return UpsertOutput(upserted=False, message=str(exc))

    return UpsertOutput(upserted=True)


def uuid4_safe() -> UUID:
    import uuid

    return uuid.uuid4()


@activity.defn(name="DeleteConsolidatedMessages")
async def delete_consolidated_messages(input: DeleteInput) -> DeleteOutput:
    """Delete CHAT_MESSAGE rows that have been consolidated (§19.28, step 4).

    STRICTLY ordered AFTER successful upsert. Temporal durable execution
    guarantees this activity only runs if UpsertMerchantChatMemory completed
    successfully. If the worker crashes between upsert and delete, the
    messages are NOT deleted — they will be re-processed on resume (§19.28).
    """
    from chat.models import ChatMessage

    period_start_dt = datetime.fromisoformat(input.period_start)
    period_end_dt = datetime.fromisoformat(input.period_end)

    deleted, _ = ChatMessage.objects.filter(
        session_id=input.session_id,
        created_at__lte=period_end_dt,
        created_at__gte=period_start_dt,
    ).delete()

    return DeleteOutput(deleted_count=deleted)


__all__ = [
    "CONSOLIDATION_AGE_DAYS",
    "DeleteInput",
    "DeleteOutput",
    "FindSessionsInput",
    "FindSessionsOutput",
    "SessionInfo",
    "SummarizeInput",
    "SummarizeOutput",
    "UpsertInput",
    "UpsertOutput",
    "delete_consolidated_messages",
    "find_sessions_to_consolidate",
    "summarize_chat_memory",
    "upsert_merchant_chat_memory",
]
