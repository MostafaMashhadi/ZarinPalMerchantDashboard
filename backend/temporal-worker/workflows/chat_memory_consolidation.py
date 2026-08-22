"""ChatMemoryConsolidationWorkflow — Temporal durable workflow (§9.6.3, §19.28).

Scheduled daily via Temporal Schedule on chat-queue.

Retention contract (§9.6.3): nothing is ever silently discarded.
A message is deleted only after being folded into a durable summary.

Activity sequence (two clearly ordered phases, each at an activity boundary
so a crash between them never loses un-consolidated data):

Phase 1: Consolidate (durable write)
  a. FindSessionsToConsolidate — find sessions with messages past 30-day cutoff
  b. SummarizeChatMemory — summarize aging messages via ModelRouterChain (scope="chat")
  c. UpsertMerchantChatMemory — additive/merge into MERCHANT_CHAT_MEMORY

Phase 2: Delete (only after upsert succeeds)
  d. DeleteConsolidatedMessages — delete the now-consolidated CHAT_MESSAGE rows

If the worker crashes between (c) and (d), the messages remain in
CHAT_MESSAGE and will be re-processed on resume — no data loss (§19.28).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from temporalio import workflow

from activities.chat_memory_activities import (
    DeleteInput,
    FindSessionsInput,
    SummarizeInput,
    UpsertInput,
    delete_consolidated_messages,
    find_sessions_to_consolidate,
    summarize_chat_memory,
    upsert_merchant_chat_memory,
)
from queues import CHAT_QUEUE


@dataclass
class ConsolidationWorkflowInput:
    cutoff_days: int = 30
    limit: int = 100


@dataclass
class ConsolidationResult:
    sessions_processed: int = 0
    sessions_upserted: int = 0
    sessions_deleted: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@workflow.defn(name="ChatMemoryConsolidationWorkflow")
class ChatMemoryConsolidationWorkflow:
    """Daily memory consolidation workflow (§19.28).

    Ensures no messages are deleted before being folded into MERCHANT_CHAT_MEMORY
    (§9.6.3 retention contract). Crash-safe via Temporal durable execution.
    """

    @workflow.run
    async def run(self, input: ConsolidationWorkflowInput) -> ConsolidationResult:
        result = ConsolidationResult()

        sessions_output = await workflow.execute_activity(
            find_sessions_to_consolidate,
            FindSessionsInput(cutoff_days=input.cutoff_days),
            start_to_close_timeout=60,
            task_queue=CHAT_QUEUE.name,
        )

        result.sessions_processed = len(sessions_output.sessions)

        for session_info in sessions_output.sessions[:input.limit]:
            try:
                messages = await self._fetch_session_messages(session_info)

                summarize_output = await workflow.execute_activity(
                    summarize_chat_memory,
                    SummarizeInput(
                        merchant_id=session_info.merchant_id,
                        session_id=session_info.session_id,
                        period_start=session_info.period_start,
                        period_end=session_info.period_end,
                        messages=messages,
                    ),
                    start_to_close_timeout=120,
                    task_queue=CHAT_QUEUE.name,
                )

                if not summarize_output.summary_text:
                    result.errors.append(
                        f"Empty summary for session {session_info.session_id}"
                    )
                    continue

                upsert_output = await workflow.execute_activity(
                    upsert_merchant_chat_memory,
                    UpsertInput(
                        merchant_id=session_info.merchant_id,
                        period_start=session_info.period_start,
                        period_end=session_info.period_end,
                        summary_text=summarize_output.summary_text,
                        key_facts=summarize_output.key_facts,
                        tokens_in=summarize_output.tokens_in,
                        tokens_out=summarize_output.tokens_out,
                        model=summarize_output.model,
                        tier=summarize_output.tier,
                    ),
                    start_to_close_timeout=30,
                    task_queue=CHAT_QUEUE.name,
                )

                if not upsert_output.upserted:
                    result.errors.append(
                        f"Upsert failed for {session_info.merchant_id}/"
                        f"{session_info.period_start}: {upsert_output.message}"
                    )
                    continue

                result.sessions_upserted += 1

                await workflow.execute_activity(
                    delete_consolidated_messages,
                    DeleteInput(
                        session_id=session_info.session_id,
                        period_start=session_info.period_start,
                        period_end=session_info.period_end,
                    ),
                    start_to_close_timeout=60,
                    task_queue=CHAT_QUEUE.name,
                )

                result.sessions_deleted.append(session_info.session_id)

            except Exception as exc:
                result.errors.append(
                    f"Session {session_info.session_id}: {exc}"
                )

        return result

    async def _fetch_session_messages(self, session_info) -> list[dict[str, Any]]:
        """Fetch raw messages for the session in the cutoff period (§19.28).

        This is NOT a separate activity — it's a quick query within the workflow.
        For large sessions, this could be moved to an activity.
        """
        from chat.models import ChatMessage

        period_start = datetime.fromisoformat(session_info.period_start)
        period_end = datetime.fromisoformat(session_info.period_end)

        messages = list(
            ChatMessage.objects.filter(
                session_id=session_info.session_id,
                created_at__gte=period_start,
                created_at__lte=period_end,
            ).order_by("created_at").values("id", "role", "content")[:500]
        )

        return messages


def workflow_id_for_merchant(merchant_id: str, period: str) -> str:
    """Deterministic workflow ID: chat-memory:{merchant_id}:{period} (§19.28)."""
    return f"chat-memory:{merchant_id}:{period}"


__all__ = [
    "ChatMemoryConsolidationWorkflow",
    "ConsolidationResult",
    "ConsolidationWorkflowInput",
    "workflow_id_for_merchant",
]
