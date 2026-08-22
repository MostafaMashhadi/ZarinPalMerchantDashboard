"""Chat session repository (§9.6.2, §19.25).

The ONLY place that touches CHAT_SESSION table.
"""

from __future__ import annotations

from uuid import UUID

from django.utils import timezone

from chat.models import ChatSession


class ChatSessionRepository:
    def create(
        self,
        merchant_id: UUID,
        merchant_user_id: UUID,
        *,
        language_hint: str = "fa",
    ) -> ChatSession:
        return ChatSession.objects.create(
            merchant_id=merchant_id,
            merchant_user_id=merchant_user_id,
            status="active",
            language_hint=language_hint,
            started_at=timezone.now(),
            last_activity_at=timezone.now(),
        )

    def get(self, session_id: UUID) -> ChatSession | None:
        try:
            return ChatSession.objects.select_related("merchant", "merchant_user").get(
                id=session_id
            )
        except ChatSession.DoesNotExist:
            return None

    def list_for_merchant(self, merchant_id: UUID) -> list[ChatSession]:
        return list(
            ChatSession.objects.filter(
                merchant_id=merchant_id, status="active"
            ).order_by("-started_at")
        )

    def update_activity(self, session: ChatSession) -> None:
        session.last_activity_at = timezone.now()
        session.save(update_fields=["last_activity_at"])

    def end(self, session: ChatSession) -> None:
        session.status = "ended"
        session.last_activity_at = timezone.now()
        session.save(update_fields=["status", "last_activity_at"])


__all__ = ["ChatSessionRepository"]
