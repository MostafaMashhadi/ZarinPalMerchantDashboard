"""ChatFacade — single shared entry point for chat orchestration (§9.6.1, §19.25).

Used by:
- REST controller (chat_controller.py) — this sprint
- MCP ask_agent tool — Sprint 4

Single point of coordination: session management, turn orchestration,
delivery strategy selection, and streaming/SSE framing.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from rest_framework.response import Response

from chat.delivery.delivery_strategy import (
    BufferedDelivery,
    StreamingDelivery,
)
from chat.models import ChatMessage, ChatSession
from chat.repositories.chat_session_repository import ChatSessionRepository
from chat.services.chat_orchestration_service import (
    ChatBudgetExceededError,
    ChatOrchestrationService,
    ChatTurnResult,
)
from facades.authz import AuthPrincipal, AuthzEnforcer
from middlewares.rate_limiter import RateLimiter


class ChatFacade:
    """Shared entry point for REST and MCP ask_agent (§9.6.1, §19.25).

    Methods:
    - create_session: POST /chat/sessions
    - send_message: POST /chat/sessions/{id}/messages (SSE or buffered)
    - list_sessions: GET /chat/sessions
    - get_history: GET /chat/sessions/{id}/messages
    """

    def __init__(
        self,
        *,
        session_repo: ChatSessionRepository | None = None,
        orchestrator: ChatOrchestrationService | None = None,
        authz: AuthzEnforcer | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._session_repo = session_repo or ChatSessionRepository()
        self._orchestrator = orchestrator or ChatOrchestrationService(
            session_repo=self._session_repo,
            rate_limiter=rate_limiter or RateLimiter(),
            authz=authz or AuthzEnforcer(),
        )
        self._authz = authz or AuthzEnforcer()

    def create_session(
        self,
        merchant_id: UUID,
        merchant_user_id: UUID,
        *,
        language_hint: str = "fa",
        principal: AuthPrincipal | None = None,
    ) -> ChatSession:
        """Create a new chat session (§9.6.1, §19.25).

        AuthZ: principal must be entitled to merchant_id.
        """
        self._authz.check_object_permission(principal, merchant_id)
        return self._session_repo.create(
            merchant_id=merchant_id,
            merchant_user_id=merchant_user_id,
            language_hint=language_hint,
        )

    def list_sessions(
        self, merchant_id: UUID, *, principal: AuthPrincipal | None = None
    ) -> list[ChatSession]:
        """List active sessions for a merchant."""
        self._authz.check_object_permission(principal, merchant_id)
        return self._session_repo.list_for_merchant(merchant_id)

    def get_history(
        self, session_id: UUID, *, principal: AuthPrincipal | None = None
    ) -> list[ChatMessage]:
        """Get chat message history for a session."""
        session = self._session_repo.get(session_id)
        if session is None:
            return []
        self._authz.check_object_permission(principal, session.merchant_id)
        from chat.repositories.chat_message_repository import ChatMessageRepository

        return ChatMessageRepository().list_for_session(session)

    def send_message(
        self,
        session_id: UUID,
        user_message: str,
        *,
        principal: AuthPrincipal | None = None,
        stream: bool = True,
    ) -> Response | ChatTurnResult:
        """Send a user message and get the assistant response (§9.6.1, §19.25).

        Returns:
        - StreamingDelivery response (SSE) by default
        - BufferedDelivery response (JSON) on fallback
        - Raises ChatBudgetExceededError if chat budget exhausted
        """
        session = self._session_repo.get(session_id)
        if session is None:
            raise ValueError("Session not found")

        result = self._orchestrator.handle_turn(
            session=session,
            user_message_content=user_message,
            principal=principal,
            stream=stream,
        )

        if stream:
            return StreamingDelivery().deliver(iter(result.chunks))
        else:
            return BufferedDelivery().deliver(iter(result.chunks))

    def send_message_stream(
        self,
        session_id: UUID,
        user_message: str,
        *,
        principal: AuthPrincipal | None = None,
    ) -> Iterator:
        """Streaming variant — yields SSE-formatted chunks (§9.6.6)."""
        session = self._session_repo.get(session_id)
        if session is None:
            raise ValueError("Session not found")

        try:
            yield from self._orchestrator.handle_turn_stream(
                session=session,
                user_message=user_message,
                principal=principal,
            )
        except ChatBudgetExceededError as exc:
            import json

            error_data = {
                "error": "CHAT_BUDGET_EXCEEDED",
                "retry_after_seconds": exc.retry_after_seconds,
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"


__all__ = ["ChatFacade"]
