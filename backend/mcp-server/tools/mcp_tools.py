"""MCP tools — merchant-scoped analytics and chat tools (§9.4, §13, §19.20, §19.21, §19.29).

Each tool:
1. Resolves merchant_ref → UUID once (merchant-scoped by construction)
2. Enforces object-level AuthZ via AuthzEnforcer
3. Calls the SAME facade the REST controllers use

Write tool: trigger_agentic_summary (§19.20)
Read tool: list_insights (§19.21)
Chat tool: ask_agent (§19.29) — uses BufferedDelivery, no SSE transport for MCP
"""

from __future__ import annotations

import os
import sys
from typing import Any
from uuid import UUID

_api_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "api"
)
_shared_dir = os.path.join(
    os.path.dirname(__file__), "..", ".."
)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)
if _shared_dir not in sys.path:
    sys.path.insert(0, _shared_dir)

from chat.delivery.delivery_strategy import BufferedDelivery  # noqa: E402
from chat.facades.chat_facade import ChatFacade  # noqa: E402
from mcp.types import Tool  # noqa: E402

from api.mcp_registry import API_KEY_SECRET  # noqa: E402
from auth.mcp_auth import McpAuthService, McpPrincipal  # noqa: E402
from facades.analytics_facade import AnalyticsFacade  # noqa: E402
from facades.authz import AuthPrincipal, AuthzEnforcer  # noqa: E402
from services.agent_orchestration_service import (  # noqa: E402
    AgentOrchestrationService,
)
from shared.merchant_ref import resolve_merchant_ref  # noqa: E402


def _principal_to_auth_principal(principal: McpPrincipal) -> AuthPrincipal:
    """Convert MCP principal to AuthPrincipal for AuthzEnforcer (§9.4)."""
    return AuthPrincipal(
        user_id=principal.user_id,
        merchant_id=principal.merchant_id,
        role=principal.role,
        email=principal.email,
    )


def _parse_principal(
    auth_header: str | None,
) -> McpPrincipal | None:
    """Extract and authenticate the principal from request headers (§9.4)."""
    api_key = None
    client_cert_dn = None

    if auth_header:
        if auth_header.startswith("ApiKey "):
            api_key = auth_header[7:]
        elif auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        else:
            api_key = auth_header

    auth_service = McpAuthService(api_key_secret=API_KEY_SECRET)
    return auth_service.authenticate(
        api_key=api_key,
        client_cert={"subject": client_cert_dn} if client_cert_dn else None,
    )


# ---------------------------------------------------------------------------
# Tool: trigger_agentic_summary (§19.20) — WRITE
# ---------------------------------------------------------------------------

TRIGGER_AGENTIC_SUMMARY: Tool = Tool(
    name="trigger_agentic_summary",
    description=(
        "Trigger an agentic insight summary for a merchant. "
        "Requires merchant_ref, kind, and optional period_start/period_end. "
        "Returns a run_id for polling the workflow status."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "merchant_ref": {
                "type": "string",
                "description": "Merchant UUID or merchant_key",
            },
            "kind": {
                "type": "string",
                "enum": [
                    "time_range", "event_impact", "cohort_retention",
                    "peer_comparison", "anomaly_detection",
                ],
                "default": "time_range",
            },
            "period_start": {"type": "string", "description": "ISO datetime"},
            "period_end": {"type": "string", "description": "ISO datetime"},
            "ingest_batch_id": {
                "type": "string",
                "description": "Optional ingest batch UUID",
            },
        },
        "required": ["merchant_ref"],
    },
)


def handle_trigger_agentic_summary(
    arguments: dict[str, Any],
    principal: McpPrincipal,
) -> dict[str, Any]:
    """Execute trigger_agentic_summary tool (§19.20).

    Calls AgentOrchestrationService.trigger_summary — same logic as REST
    POST /merchants/{ref}/agent/trigger-summary.
    """
    from datetime import datetime, timedelta

    merchant_ref = arguments.get("merchant_ref")
    if merchant_ref is None:
        return {
            "error": "MERCHANT_NOT_FOUND",
            "code": "merchant_not_found",
        }

    merchant_id = resolve_merchant_ref(merchant_ref)
    if merchant_id is None:
        return {
            "error": "MERCHANT_NOT_FOUND",
            "code": "merchant_not_found",
        }

    auth_principal = _principal_to_auth_principal(principal)
    enforcer = AuthzEnforcer()
    enforcer.check_object_permission(auth_principal, merchant_id)

    kind = arguments.get("kind", "time_range")
    period_start_str = arguments.get("period_start")
    period_end_str = arguments.get("period_end")

    if period_start_str:
        period_start = datetime.fromisoformat(period_start_str)
    else:
        period_start = datetime.now() - timedelta(days=30)

    if period_end_str:
        period_end = datetime.fromisoformat(period_end_str)
    else:
        period_end = datetime.now()

    ingest_batch_id = arguments.get("ingest_batch_id")
    if ingest_batch_id:
        ingest_batch_id = UUID(ingest_batch_id)

    service = AgentOrchestrationService()
    result = service.trigger_summary(
        merchant_id=merchant_id,
        kind=kind,
        period_start=period_start,
        period_end=period_end,
        idempotency_key=f"mcp:{principal.user_id}:{merchant_ref}:{kind}",
        principal=auth_principal,
        ingest_batch_id=ingest_batch_id,
    )

    return result


# ---------------------------------------------------------------------------
# Tool: list_insights (§19.21) — READ
# ---------------------------------------------------------------------------

LIST_INSIGHTS: Tool = Tool(
    name="list_insights",
    description=(
        "List insights for a merchant. "
        "Supports optional kind filter and pagination. "
        "Pagination defaults: limit=20, offset=0 (same as REST)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "merchant_ref": {
                "type": "string",
                "description": "Merchant UUID or merchant_key",
            },
            "kind": {
                "type": "string",
                "description": "Filter by insight kind",
            },
            "limit": {"type": "integer", "default": 20, "minimum": 1, "max": 100},
            "offset": {"type": "integer", "default": 0, "minimum": 0},
        },
        "required": ["merchant_ref"],
    },
)


def handle_list_insights(
    arguments: dict[str, Any],
    principal: McpPrincipal,
) -> dict[str, Any]:
    """Execute list_insights tool (§19.21).

    Calls AnalyticsFacade.list_insights — same pagination defaults and
    AuthZ as REST GET /merchants/{ref}/insights.
    """
    merchant_ref = arguments.get("merchant_ref")
    if merchant_ref is None:
        return {
            "error": "MERCHANT_NOT_FOUND",
            "code": "merchant_not_found",
        }

    merchant_id = resolve_merchant_ref(merchant_ref)
    if merchant_id is None:
        return {
            "error": "MERCHANT_NOT_FOUND",
            "code": "merchant_not_found",
        }

    auth_principal = _principal_to_auth_principal(principal)
    enforcer = AuthzEnforcer()
    enforcer.check_object_permission(auth_principal, merchant_id)

    kind = arguments.get("kind")
    limit = int(arguments.get("limit", 20))
    offset = int(arguments.get("offset", 0))

    if limit > 100:
        limit = 100

    facade = AnalyticsFacade()
    insights = facade.list_insights(
        merchant_id=merchant_id,
        kind=kind,
        limit=limit,
        offset=offset,
        principal=auth_principal,
    )

    return {"insights": insights, "count": len(insights)}


# ---------------------------------------------------------------------------
# Tool: ask_agent (§19.29) — CHAT
# ---------------------------------------------------------------------------

ASK_AGENT: Tool = Tool(
    name="ask_agent",
    description=(
        "Ask the merchant's AI agent a question. "
        "Requires merchant_ref and message. "
        "Optional session_id to continue a conversation. "
        "Returns the complete buffered answer with session_id, "
        "referenced_insight_ids, and metadata. "
        "Uses BufferedDelivery — no SSE over MCP (§6.6, §9.6.7)."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "merchant_ref": {
                "type": "string",
                "description": "Merchant UUID or merchant_key",
            },
            "session_id": {
                "type": "string",
                "description": "Optional: existing chat session UUID. "
                               "If omitted, a new session is created.",
            },
            "message": {
                "type": "string",
                "description": "The user's question or message",
            },
            "language_hint": {
                "type": "string",
                "description": "Preferred language (default: fa)",
                "default": "fa",
            },
        },
        "required": ["merchant_ref", "message"],
    },
)


def handle_ask_agent(
    arguments: dict[str, Any],
    principal: McpPrincipal,
) -> dict[str, Any]:
    """Execute ask_agent tool (§19.29, §9.6.7).

    Calls ChatFacade — identical path to browser chat REST call.
    - Creates a session if session_id is omitted
    - Uses BufferedDelivery (stream=False) — MCP has no SSE transport
    - Shares the same chat-scope cost ledger and rate-limit bucket
      as the browser path — no separate MCP chat budget
    """
    merchant_ref = arguments.get("merchant_ref")
    if merchant_ref is None:
        return {
            "error": "MERCHANT_NOT_FOUND",
            "code": "merchant_not_found",
        }

    merchant_id = resolve_merchant_ref(merchant_ref)
    if merchant_id is None:
        return {
            "error": "MERCHANT_NOT_FOUND",
            "code": "merchant_not_found",
        }

    auth_principal = _principal_to_auth_principal(principal)
    enforcer = AuthzEnforcer()
    enforcer.check_object_permission(auth_principal, merchant_id)

    user_message = arguments.get("message", "").strip()
    if not user_message:
        return {
            "error": "INVALID_MESSAGE",
            "code": "invalid_message",
        }

    session_id_str = arguments.get("session_id")
    language_hint = arguments.get("language_hint", "fa")

    facade = ChatFacade()

    if session_id_str:
        session = facade._session_repo.get(UUID(session_id_str))
        if session is None:
            return {
                "error": "SESSION_NOT_FOUND",
                "code": "session_not_found",
            }
    else:
        session = facade.create_session(
            merchant_id=merchant_id,
            merchant_user_id=principal.user_id,
            language_hint=language_hint,
            principal=auth_principal,
        )

    from chat.services.chat_orchestration_service import (
        ChatBudgetExceededError,
    )

    try:
        turn_result = facade._orchestrator.handle_turn(
            session=session,
            user_message_content=user_message,
            principal=auth_principal,
            stream=False,
        )
    except ChatBudgetExceededError as exc:
        return {
            "error": "CHAT_BUDGET_EXCEEDED",
            "code": "budget_exceeded",
            "retry_after_seconds": getattr(
                exc, "retry_after_seconds", 3600
            ),
        }

    buffered_response = BufferedDelivery().deliver(iter(turn_result.chunks))
    result_data = dict(buffered_response.data) if hasattr(buffered_response, "data") else {}

    return {
        "session_id": str(session.id),
        "text": result_data.get("text", ""),
        "claims": result_data.get("claims", []),
        "tokens_in": result_data.get("tokens_in", 0),
        "tokens_out": result_data.get("tokens_out", 0),
        "model": result_data.get("model", ""),
        "tier": result_data.get("tier", ""),
        "referenced_insight_ids": turn_result.referenced_insight_ids,
    }


__all__ = [
    "ASK_AGENT",
    "LIST_INSIGHTS",
    "TRIGGER_AGENTIC_SUMMARY",
    "handle_ask_agent",
    "handle_list_insights",
    "handle_trigger_agentic_summary",
]
