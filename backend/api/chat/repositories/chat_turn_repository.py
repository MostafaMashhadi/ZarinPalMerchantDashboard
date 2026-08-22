"""Chat turn step repository (§9.6.2, §19.25, §19.27).

The ONLY place that touches CHAT_TURN_STEP table.

Implements idempotent resume: check_or_create_turn(message_key) looks up
a completed step by checkpoint_id; if found, returns the saved state —
allowing crash-and-retry resumption without re-executing expensive steps.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from chat.models import ChatMessage, ChatTurnStep


class ChatTurnRepository:
    def check_or_create_turn(
        self,
        message: ChatMessage,
        step_name: str,
        *,
        checkpoint_id: str | None = None,
    ) -> ChatTurnStep | None:
        """Check if a step has already been completed (§10.2, §19.27).

        If a completed step exists for the given checkpoint_id (or
        step_name+message), return its saved checkpoint_state so the
        orchestrator can resume from that point.

        Otherwise, create a new in-progress step and return None
        to signal that the step has not yet been executed.
        """
        query = {"message": message, "step_name": step_name, "status": "completed"}
        if checkpoint_id:
            query["checkpoint_state__checkpoint_id"] = checkpoint_id

        try:
            completed = ChatTurnStep.objects.get(**query)
            return completed
        except ChatTurnStep.DoesNotExist:
            pass

        existing = ChatTurnStep.objects.filter(
            message=message, step_name=step_name
        ).first()
        if existing and existing.status == "in_progress":
            existing.status = "failed"
            existing.save(update_fields=["status"])

        return None

    def create_step(
        self,
        message: ChatMessage,
        step_name: str,
        *,
        checkpoint_id: str | None = None,
    ) -> ChatTurnStep:
        return ChatTurnStep.objects.create(
            message=message,
            step_name=step_name,
            status="in_progress",
            checkpoint_state={"checkpoint_id": checkpoint_id} if checkpoint_id else {},
            cost_usd=0,
            executed_at=timezone.now(),
        )

    def mark_completed(
        self, step: ChatTurnStep, *, checkpoint_state: dict[str, Any] | None = None
    ) -> None:
        step.status = "completed"
        if checkpoint_state:
            merged = {**step.checkpoint_state, **checkpoint_state}
            step.checkpoint_state = merged
        step.executed_at = timezone.now()
        step.save(update_fields=["status", "checkpoint_state", "executed_at"])

    def mark_failed(self, step: ChatTurnStep) -> None:
        step.status = "failed"
        step.executed_at = timezone.now()
        step.save(update_fields=["status", "executed_at"])

    def get_latest_step(self, message: ChatMessage) -> ChatTurnStep | None:
        return ChatTurnStep.objects.filter(message=message).order_by("-executed_at").first()

    def record_cost(self, step: ChatTurnStep, cost_usd: float) -> None:
        step.cost_usd = cost_usd
        step.save(update_fields=["cost_usd"])


__all__ = ["ChatTurnRepository"]
