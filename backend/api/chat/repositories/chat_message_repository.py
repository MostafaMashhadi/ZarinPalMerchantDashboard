"""Chat message repository (§9.6.2, §19.25).

The ONLY place that touches CHAT_MESSAGE table.
"""

from __future__ import annotations

from uuid import UUID

from django.utils import timezone

from chat.models import ChatMessage, ChatSession


class ChatMessageRepository:
    def create(
        self,
        session: ChatSession,
        role: str,
        content: str,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model_used: str = "",
        delivery_mode: str = "buffered",
        referenced_insight_ids: list[str] | None = None,
    ) -> ChatMessage:
        return ChatMessage.objects.create(
            session=session,
            role=role,
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model_used=model_used,
            delivery_mode=delivery_mode,
            created_at=timezone.now(),
            referenced_insight_ids=referenced_insight_ids or [],
        )

    def get(self, message_id: UUID) -> ChatMessage | None:
        try:
            return ChatMessage.objects.get(id=message_id)
        except ChatMessage.DoesNotExist:
            return None

    def list_for_session(self, session: ChatSession) -> list[ChatMessage]:
        return list(
            ChatMessage.objects.filter(session=session).order_by("created_at")
        )

    def update_referenced_insights(
        self, message: ChatMessage, insight_ids: list[str]
    ) -> None:
        message.referenced_insight_ids = insight_ids
        message.save(update_fields=["referenced_insight_ids"])

    def update_stats(
        self,
        message: ChatMessage,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model_used: str = "",
        delivery_mode: str = "buffered",
    ) -> None:
        message.tokens_in = tokens_in
        message.tokens_out = tokens_out
        if model_used:
            message.model_used = model_used
        message.delivery_mode = delivery_mode
        message.save(update_fields=["tokens_in", "tokens_out", "model_used", "delivery_mode"])


__all__ = ["ChatMessageRepository"]
