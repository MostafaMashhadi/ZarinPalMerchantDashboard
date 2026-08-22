"""Chat API endpoints (§9.6, §11 API Contract).

POST /chat/sessions              — create a new chat session
GET  /chat/sessions              — list active sessions for the authenticated merchant
GET  /chat/sessions/{id}/messages — get message history
POST /chat/sessions/{id}/messages  — send a message (SSE by default, JSON on buffered)
"""

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.facades.chat_facade import ChatFacade
from chat.services.chat_orchestration_service import ChatBudgetExceededError
from facades.authz import AuthPrincipal


def _get_principal(request: Request) -> AuthPrincipal | None:
    return getattr(request, "auth_principal", None)


def _error_response(error: str, status_code: int) -> Response:
    return Response({"error": error}, status=status_code)


class ChatSessionListController(APIView):
    """POST /chat/sessions — create a new session.
    GET  /chat/sessions — list sessions.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._facade: ChatFacade | None = None

    def _get_facade(self) -> ChatFacade:
        if self._facade is None:
            self._facade = ChatFacade()
        return self._facade

    def post(self, request: Request) -> Response:
        principal = _get_principal(request)
        if principal is None:
            return _error_response("AUTHENTICATION_REQUIRED", status.HTTP_401_UNAUTHORIZED)

        language_hint = request.data.get("language_hint", "fa")
        session = self._get_facade().create_session(
            merchant_id=principal.merchant_id,
            merchant_user_id=principal.user_id,
            language_hint=language_hint,
            principal=principal,
        )
        return Response(
            {
                "session_id": str(session.id),
                "merchant_id": str(session.merchant_id),
                "started_at": session.started_at.isoformat() if session.started_at else None,
            },
            status=status.HTTP_201_CREATED,
        )

    def get(self, request: Request) -> Response:
        principal = _get_principal(request)
        if principal is None:
            return _error_response("AUTHENTICATION_REQUIRED", status.HTTP_401_UNAUTHORIZED)

        sessions = self._get_facade().list_sessions(
            merchant_id=principal.merchant_id, principal=principal
        )
        return Response(
            {
                "sessions": [
                    {
                        "id": str(s.id),
                        "status": s.status,
                        "started_at": (
                            s.started_at.isoformat() if s.started_at else None
                        ),
                        "last_activity_at": (
                            s.last_activity_at.isoformat()
                            if s.last_activity_at else None
                        ),
                        "language_hint": s.language_hint,
                    }
                    for s in sessions
                ]
            }
        )


class ChatSessionMessagesController(APIView):
    """GET  /chat/sessions/{id}/messages — message history.
    POST /chat/sessions/{id}/messages — send a message (SSE by default).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._facade: ChatFacade | None = None

    def _get_facade(self) -> ChatFacade:
        if self._facade is None:
            self._facade = ChatFacade()
        return self._facade

    def get(self, request: Request, session_id: str) -> Response:
        principal = _get_principal(request)
        if principal is None:
            return _error_response("AUTHENTICATION_REQUIRED", status.HTTP_401_UNAUTHORIZED)

        try:
            sid = UUID(session_id)
        except (ValueError, TypeError):
            return _error_response("INVALID_SESSION_ID", status.HTTP_400_BAD_REQUEST)

        messages = self._get_facade().get_history(sid, principal=principal)
        return Response(
            {
                "messages": [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "tokens_in": m.tokens_in,
                        "tokens_out": m.tokens_out,
                        "model_used": m.model_used,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                        "referenced_insight_ids": m.referenced_insight_ids,
                    }
                    for m in messages
                ]
            }
        )

    def post(self, request: Request, session_id: str) -> Response:
        principal = _get_principal(request)
        if principal is None:
            return _error_response("AUTHENTICATION_REQUIRED", status.HTTP_401_UNAUTHORIZED)

        try:
            sid = UUID(session_id)
        except (ValueError, TypeError):
            return _error_response("INVALID_SESSION_ID", status.HTTP_400_BAD_REQUEST)

        user_message = request.data.get("message", "")
        if not user_message or not isinstance(user_message, str):
            return _error_response("MESSAGE_REQUIRED", status.HTTP_400_BAD_REQUEST)

        buffered = request.query_params.get("buffered", "false").lower() == "true"
        stream = not buffered

        try:
            if stream:
                result = self._get_facade().send_message_stream(
                    session_id=sid,
                    user_message=user_message,
                    principal=principal,
                )
                return Response(
                    streaming_content=result,
                    content_type="text/event-stream",
                )
            else:
                result = self._get_facade().send_message(
                    session_id=sid,
                    user_message=user_message,
                    principal=principal,
                    stream=False,
                )
                return result
        except ChatBudgetExceededError:
            return _error_response(
                "CHAT_BUDGET_EXCEEDED",
                status.HTTP_503_UNAVAILABLE,
            )
        except ValueError as exc:
            if "not found" in str(exc):
                return _error_response("SESSION_NOT_FOUND", status.HTTP_404_NOT_FOUND)
            return _error_response(str(exc), status.HTTP_400_BAD_REQUEST)


__all__ = [
    "ChatSessionListController",
    "ChatSessionMessagesController",
]
