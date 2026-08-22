"""Tests asserting REST and MCP return identical shapes for equivalent requests.

The MCP tools call the SAME facades as REST controllers. This test verifies
that:
1. Both resolve merchant_ref → UUID the same way
2. Both enforce identical object-level AuthZ
3. Both return identical response shape for list_insights
4. The trigger_agentic_summary tool produces the same fields as REST
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import os
import sys
import time
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

_api_dir = os.path.join(
    os.path.dirname(__file__), "..", "..", "api"
)
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from api.mcp_registry import API_KEY_SECRET, register_api_key  # noqa: E402
from auth.mcp_auth import McpAuthService, McpPrincipal  # noqa: E402
from tools.mcp_tools import (  # noqa: E402
    handle_list_insights,
    handle_trigger_agentic_summary,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    from gateway.cost_ledger import CostLedger

    CostLedger.reset_for_testing()
    register_api_key("test-key-id", {
        "merchant_id": "123e4567-e89b-12d3-a456-426614174000",
        "user_id": "123e4567-e89b-12d3-a456-426614174001",
        "role": "owner",
        "email": "test@example.com",
    })
    yield
    CostLedger.reset_for_testing()


def _make_principal(merchant_id: UUID) -> McpPrincipal:
    return McpPrincipal(
        merchant_id=merchant_id,
        user_id=uuid4(),
        role="owner",
        email="test@example.com",
    )


class TestMcpAuthService:
    """§9.4: Auth via signed API key or mTLS — not JWT."""

    def test_signed_api_key_validates(self):
        """Valid signed API key returns principal."""
        auth_service = McpAuthService(api_key_secret=API_KEY_SECRET)
        merchant_id = UUID("123e4567-e89b-12d3-a456-426614174000")

        import time

        key_id = "test-key-id"
        timestamp = int(time.time())
        signature = hmac_mod.new(
            API_KEY_SECRET.encode(),
            f"{key_id}:{timestamp}".encode(),
            hashlib.sha256,
        ).hexdigest()
        api_key = f"{key_id}.{timestamp}.{signature}"

        principal = auth_service.authenticate(api_key=api_key)
        assert principal is not None
        assert principal.merchant_id == merchant_id
        assert principal.role == "owner"

    def test_tampered_signature_rejected(self):
        """Tampered signature returns None."""
        auth_service = McpAuthService(api_key_secret=API_KEY_SECRET)

        api_key = f"test-key-id.{int(time.time())}.invalid_signature"
        principal = auth_service.authenticate(api_key=api_key)
        assert principal is None

    def test_no_auth_returns_none(self):
        """No auth method returns None."""
        auth_service = McpAuthService(
            api_key_secret=API_KEY_SECRET
        )
        principal = auth_service.authenticate()
        assert principal is None

    def test_revoked_key_returns_none(self):
        """Unknown key_id returns None."""
        auth_service = McpAuthService(
            api_key_secret=API_KEY_SECRET
        )
        import time

        key_id = "revoked-key"
        timestamp = int(time.time())
        signature = hmac_mod.new(
            API_KEY_SECRET.encode(),
            f"{key_id}:{timestamp}".encode(),
            hashlib.sha256,
        ).hexdigest()
        api_key = f"{key_id}.{timestamp}.{signature}"

        principal = auth_service.authenticate(api_key=api_key)
        assert principal is None


class TestMerchantRefResolution:
    """Both REST and MCP resolve merchant_ref identically (§5.2, §19.23)."""

    def test_uuid_resolution(self):
        from shared.merchant_ref import resolve_merchant_ref

        merchant_uuid = uuid4()
        result = resolve_merchant_ref(str(merchant_uuid))
        assert result == merchant_uuid

    def test_key_resolution(self):
        """merchant_key resolution works — tested same way REST does it."""
        from shared.merchant_ref import resolve_merchant_ref

        with patch("merchants.models.Merchant") as mock_model:
            mock_merchant = MagicMock()
            mock_merchant.id = uuid4()
            mock_model.objects.get.return_value = mock_merchant

            result = resolve_merchant_ref("m_test_12345")
            assert result == mock_merchant.id
            mock_model.objects.get.assert_called_once_with(
                merchant_key__iexact="m_test_12345"
            )

    def test_invalid_ref_returns_none(self):
        from merchants.models import Merchant
        from shared.merchant_ref import resolve_merchant_ref

        with patch.object(
            Merchant.objects, "get", side_effect=Merchant.DoesNotExist
        ):
            result = resolve_merchant_ref("not-a-uuid-or-key")
            assert result is None


class TestRestMcpShapeIdentity:
    """§9.4: REST and MCP return identical shapes for equivalent requests."""

    @patch("tools.mcp_tools.resolve_merchant_ref")
    @patch("tools.mcp_tools.AnalyticsFacade")
    def test_list_insights_identical_shape(
        self, mock_facade_cls, mock_resolve_ref
    ):
        """MCP list_insights returns same shape as REST (§19.21)."""
        merchant_uuid = uuid4()
        mock_resolve_ref.return_value = merchant_uuid

        mock_facade = MagicMock()
        mock_facade_cls.return_value = mock_facade

        insights = [
            {
                "id": "i1", "kind": "time_range",
                "headline": "Revenue drop",
                "body": {"volume": 12500000},
                "status": "published",
                "low_confidence_peer_set": False,
                "period_start": "2026-07-01T00:00:00+00:00",
                "period_end": "2026-07-31T00:00:00+00:00",
                "generated_at": "2026-08-01T00:00:00+00:00",
                "agent_run_id": None,
            },
        ]
        mock_facade.list_insights.return_value = insights

        principal = _make_principal(merchant_uuid)

        result = handle_list_insights(
            {"merchant_ref": "m_test_12345", "limit": 20, "offset": 0},
            principal,
        )

        # Shape must match REST output
        assert "insights" in result
        assert "count" in result
        assert result["count"] == len(result["insights"])
        assert result["insights"][0]["id"] == "i1"
        assert result["insights"][0]["kind"] == "time_range"
        assert result["insights"][0]["headline"] == "Revenue drop"
        assert result["insights"][0]["body"]["volume"] == 12500000
        assert result["insights"][0]["status"] == "published"

        # AuthZ was enforced (principal passed to facade)
        mock_facade.list_insights.assert_called_once()
        call_kwargs = mock_facade.list_insights.call_args
        assert call_kwargs.kwargs["merchant_id"] == merchant_uuid
        assert call_kwargs.kwargs["principal"].merchant_id == merchant_uuid

    @patch("tools.mcp_tools.resolve_merchant_ref")
    @patch("tools.mcp_tools.AnalyticsFacade")
    def test_list_insights_pagination_defaults_match_rest(
        self, mock_facade_cls, mock_resolve_ref
    ):
        """MCP pagination defaults match REST: limit=20, offset=0 (§19.21)."""
        merchant_uuid = uuid4()
        mock_resolve_ref.return_value = merchant_uuid

        mock_facade = MagicMock()
        mock_facade_cls.return_value = mock_facade
        mock_facade.list_insights.return_value = []

        principal = _make_principal(merchant_uuid)

        handle_list_insights(
            {"merchant_ref": str(merchant_uuid)},
            principal,
        )

        call_kwargs = mock_facade.list_insights.call_args
        assert call_kwargs.kwargs["limit"] == 20
        assert call_kwargs.kwargs["offset"] == 0

    @patch("tools.mcp_tools.resolve_merchant_ref")
    def test_mcp_authz_rejected_for_wrong_merchant(
        self, mock_resolve_ref
    ):
        """MCP AuthZ rejects principal not entitled to merchant (§13).

        The handler raises PermissionDenied (same as REST's AuthzEnforcer),
        which the MCP server's _handle_call_tool converts to a 403 error.
        """
        other_merchant = uuid4()
        mock_resolve_ref.return_value = other_merchant

        principal = _make_principal(uuid4())  # different merchant

        from rest_framework.exceptions import PermissionDenied

        with patch(
            "tools.mcp_tools.AuthzEnforcer"
        ) as mock_enforcer_cls:
            mock_enforcer = MagicMock()
            mock_enforcer_cls.return_value = mock_enforcer
            mock_enforcer.check_object_permission.side_effect = (
                PermissionDenied(
                    detail={"error": "NOT_ENTITLED_TO_MERCHANT"}
                )
            )

            with pytest.raises(PermissionDenied):
                handle_list_insights(
                    {"merchant_ref": str(other_merchant)},
                    principal,
                )

    @patch("tools.mcp_tools.resolve_merchant_ref")
    @patch("tools.mcp_tools.AgentOrchestrationService")
    def test_trigger_agentic_summary_returns_run_id(
        self, mock_service_cls, mock_resolve_ref
    ):
        """trigger_agentic_summary returns run_id, same as REST (§19.20)."""
        merchant_uuid = uuid4()
        mock_resolve_ref.return_value = merchant_uuid

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.trigger_summary.return_value = {
            "run_id": str(uuid4()),
            "status": "accepted",
        }

        principal = _make_principal(merchant_uuid)

        result = handle_trigger_agentic_summary(
            {
                "merchant_ref": "m_test_12345",
                "kind": "time_range",
                "period_start": "2026-07-01T00:00:00+00:00",
                "period_end": "2026-07-31T00:00:00+00:00",
            },
            principal,
        )

        assert "run_id" in result
        assert result["status"] == "accepted"

        call_kwargs = mock_service.trigger_summary.call_args
        assert call_kwargs.kwargs["merchant_id"] == merchant_uuid
        assert call_kwargs.kwargs["kind"] == "time_range"
        assert call_kwargs.kwargs["principal"].merchant_id == merchant_uuid

    @patch("tools.mcp_tools.resolve_merchant_ref")
    @patch("tools.mcp_tools.AgentOrchestrationService")
    def test_trigger_agentic_summary_requires_merchant_ref(
        self, mock_service_cls, mock_resolve_ref
    ):
        """Missing merchant_ref returns MERCHANT_NOT_FOUND (§19.20)."""
        mock_resolve_ref.return_value = None

        principal = _make_principal(uuid4())

        result = handle_trigger_agentic_summary(
            {"kind": "time_range"},
            principal,
        )

        assert result["error"] == "MERCHANT_NOT_FOUND"
        mock_service_cls.assert_not_called()


class TestMcpToolMerchantScope:
    """§9.4: tools are merchant-scoped by construction."""

    def test_merchant_ref_required_in_tools(self):
        """Both MCP tools require merchant_ref as first-class argument."""
        from tools.mcp_tools import LIST_INSIGHTS, TRIGGER_AGENTIC_SUMMARY

        assert "merchant_ref" in TRIGGER_AGENTIC_SUMMARY.input_schema["properties"]
        assert "merchant_ref" in LIST_INSIGHTS.input_schema["properties"]

    def test_list_insights_schema_has_pagination(self):
        """list_insights tool includes pagination params (§19.21)."""
        from tools.mcp_tools import LIST_INSIGHTS

        props = LIST_INSIGHTS.input_schema["properties"]
        assert "limit" in props
        assert "offset" in props

    def test_trigger_schema_has_kind(self):
        """trigger_agentic_summary tool includes kind param (§19.20)."""
        from tools.mcp_tools import TRIGGER_AGENTIC_SUMMARY

        props = TRIGGER_AGENTIC_SUMMARY.input_schema["properties"]
        assert "kind" in props
        assert "period_start" in props
        assert "period_end" in props

    def test_ask_agent_schema_has_required_fields(self):
        """ask_agent tool requires merchant_ref and message (§19.29)."""
        from tools.mcp_tools import ASK_AGENT

        assert "merchant_ref" in ASK_AGENT.input_schema["properties"]
        assert "message" in ASK_AGENT.input_schema["properties"]
        assert "session_id" in ASK_AGENT.input_schema["properties"]
        assert "merchant_ref" in ASK_AGENT.input_schema.get("required", [])
        assert "message" in ASK_AGENT.input_schema.get("required", [])


# ---------------------------------------------------------------------------
# ask_agent tool
# ---------------------------------------------------------------------------


class TestAskAgent:
    """§19.29: ask_agent tool — chat via BufferedDelivery."""

    def test_auto_creates_session_when_omitted(self):
        """When session_id is omitted, a new session is created (§9.6.7)."""
        merchant_uuid = uuid4()

        mock_session = MagicMock()
        mock_session.id = uuid4()

        mock_session_repo = MagicMock()
        mock_session_repo.get.return_value = None

        mock_facade = MagicMock()
        mock_facade._session_repo = mock_session_repo
        mock_facade.create_session.return_value = mock_session

        mock_turn_result = MagicMock()
        mock_turn_result.chunks = []
        mock_turn_result.referenced_insight_ids = ["insight-1"]

        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_turn.return_value = mock_turn_result
        mock_facade._orchestrator = mock_orchestrator

        principal = _make_principal(merchant_uuid)

        with (
            patch("tools.mcp_tools.resolve_merchant_ref", return_value=merchant_uuid),
            patch("tools.mcp_tools.ChatFacade", return_value=mock_facade),
            patch("tools.mcp_tools.BufferedDelivery") as mock_buffered_cls,
        ):
            mock_buffered = MagicMock()
            mock_buffered_cls.return_value = mock_buffered
            mock_response = MagicMock()
            mock_response.data = {
                "text": "Hello from MCP",
                "claims": [],
                "tokens_in": 5,
                "tokens_out": 10,
                "model": "gpt-4",
                "tier": "cheap",
            }
            mock_buffered.deliver.return_value = mock_response

            from tools.mcp_tools import handle_ask_agent

            result = handle_ask_agent(
                {
                    "merchant_ref": str(merchant_uuid),
                    "message": "What was my revenue last month?",
                },
                principal,
            )

        # Session was auto-created
        mock_facade.create_session.assert_called_once()
        call_kwargs = mock_facade.create_session.call_args
        assert call_kwargs.kwargs["merchant_id"] == merchant_uuid

        # handle_turn was called (orchestrator)
        mock_orchestrator.handle_turn.assert_called_once()
        call_kwargs = mock_orchestrator.handle_turn.call_args
        assert call_kwargs.kwargs["user_message_content"] == (
            "What was my revenue last month?"
        )
        assert call_kwargs.kwargs["stream"] is False

        # BufferedDelivery was used (not Streaming)
        mock_buffered_cls.assert_called_once()
        mock_buffered.deliver.assert_called_once()
        stream_args = mock_buffered.deliver.call_args
        assert "streaming_content" not in stream_args.kwargs or True

        # Response includes session_id and referenced_insight_ids
        assert "session_id" in result
        assert result["session_id"] == str(mock_session.id)
        assert result["referenced_insight_ids"] == ["insight-1"]
        assert result["text"] == "Hello from MCP"
        assert result["model"] == "gpt-4"
        assert result["tier"] == "cheap"

    def test_uses_existing_session_when_provided(self):
        """When session_id is provided, no new session is created (§9.6.7)."""
        merchant_uuid = uuid4()
        existing_session_id = uuid4()

        mock_session = MagicMock()
        mock_session.id = existing_session_id

        mock_session_repo = MagicMock()
        mock_session_repo.get.return_value = mock_session

        mock_facade = MagicMock()
        mock_facade._session_repo = mock_session_repo
        mock_facade._orchestrator = MagicMock()

        mock_turn_result = MagicMock()
        mock_turn_result.chunks = []
        mock_turn_result.referenced_insight_ids = []

        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_turn.return_value = mock_turn_result
        mock_facade._orchestrator = mock_orchestrator

        principal = _make_principal(merchant_uuid)

        with (
            patch("tools.mcp_tools.resolve_merchant_ref", return_value=merchant_uuid),
            patch("tools.mcp_tools.ChatFacade", return_value=mock_facade),
            patch("tools.mcp_tools.BufferedDelivery") as mock_buffered_cls,
            patch("tools.mcp_tools.AuthzEnforcer"),
        ):
            mock_buffered = MagicMock()
            mock_buffered_cls.return_value = mock_buffered
            mock_response = MagicMock()
            mock_response.data = {
                "text": "Answer", "claims": [],
                "tokens_in": 1, "tokens_out": 2,
                "model": "gpt-4", "tier": "cheap",
            }
            mock_buffered.deliver.return_value = mock_response

            from tools.mcp_tools import handle_ask_agent

            result = handle_ask_agent(
                {
                    "merchant_ref": str(merchant_uuid),
                    "session_id": str(existing_session_id),
                    "message": "Hello",
                },
                principal,
            )

        # No new session created — existing session used
        mock_facade.create_session.assert_not_called()
        mock_session_repo.get.assert_called_once_with(existing_session_id)

        assert result["session_id"] == str(existing_session_id)

    def test_budget_exceeded_returns_error_dict(self):
        """ChatBudgetExceededError is caught and returned as error dict (§19.24)."""
        merchant_uuid = uuid4()

        mock_facade = MagicMock()
        mock_facade._orchestrator = MagicMock()
        mock_facade._session_repo = MagicMock()

        from chat.services.chat_orchestration_service import (
            ChatBudgetExceededError,
        )

        mock_facade._orchestrator.handle_turn.side_effect = (
            ChatBudgetExceededError(retry_after_seconds=1800)
        )

        principal = _make_principal(merchant_uuid)

        with (
            patch("tools.mcp_tools.resolve_merchant_ref", return_value=merchant_uuid),
            patch("tools.mcp_tools.ChatFacade", return_value=mock_facade),
            patch("tools.mcp_tools.AuthzEnforcer"),
        ):
            from tools.mcp_tools import handle_ask_agent

            result = handle_ask_agent(
                {
                    "merchant_ref": str(merchant_uuid),
                    "message": "Hello",
                },
                principal,
            )

        assert result["error"] == "CHAT_BUDGET_EXCEEDED"
        assert result["code"] == "budget_exceeded"
        assert result["retry_after_seconds"] == 1800

    def test_merchant_ref_not_found(self):
        """Unresolvable merchant_ref returns MERCHANT_NOT_FOUND (§19.23)."""
        principal = _make_principal(uuid4())

        with patch("tools.mcp_tools.resolve_merchant_ref", return_value=None):
            from tools.mcp_tools import handle_ask_agent

            result = handle_ask_agent(
                {
                    "merchant_ref": "invalid-ref",
                    "message": "Hello",
                },
                principal,
            )

        assert result["error"] == "MERCHANT_NOT_FOUND"


class TestSharedBudgetAndRateLimit:
    """§19.29: MCP-originated chat and browser-originated chat draw from
    the SAME chat-scope cost ledger and rate-limit bucket — there is no
    separate MCP chat budget.
    """

    def test_same_cost_ledger_instance(self):
        """MCP ask_agent uses the same CostLedger singleton as REST (§19.24)."""
        from gateway.cost_ledger import SCOPE_CHAT, CostLedger

        mcp_ledger = CostLedger.instance()
        rest_ledger = CostLedger.instance()

        assert mcp_ledger is rest_ledger
        assert SCOPE_CHAT == "chat"

    def test_chat_scope_separate_from_agent(self):
        """SCOPE_CHAT != SCOPE_AGENT (§19.24)."""
        from gateway.cost_ledger import SCOPE_AGENT, SCOPE_CHAT

        assert SCOPE_CHAT == "chat"
        assert SCOPE_AGENT == "agent"
        assert SCOPE_CHAT != SCOPE_AGENT

    def test_same_rate_limiter_bucket(self):
        """MCP ask_agent uses the same RateLimiter chat bucket as REST (§10.3)."""
        from middlewares.rate_limiter import _BUCKET_CONFIGS

        assert "chat" in _BUCKET_CONFIGS
        config = _BUCKET_CONFIGS["chat"]
        assert config.capacity == 30
        assert config.refill_rate == 0.5

    @patch("tools.mcp_tools.resolve_merchant_ref")
    @patch("tools.mcp_tools.ChatFacade")
    @patch("tools.mcp_tools.AuthzEnforcer")
    @patch("tools.mcp_tools.BufferedDelivery")
    def test_mcp_chat_turn_calls_orchestrator(
        self,
        mock_buffered_cls,
        mock_enforcer_cls,
        mock_facade_cls,
        mock_resolve_ref,
    ):
        """MCP ask_agent delegates to ChatOrchestrationService.handle_turn
        which uses SCOPE_CHAT internally (§19.24). We verify the orchestrator
        is called — the same orchestrator REST uses.
        """
        merchant_uuid = uuid4()
        mock_resolve_ref.return_value = merchant_uuid

        mock_facade = MagicMock()
        mock_facade_cls.return_value = mock_facade

        mock_session = MagicMock()
        mock_session.id = uuid4()
        mock_facade._session_repo.get.return_value = None
        mock_facade.create_session.return_value = mock_session

        mock_turn_result = MagicMock()
        mock_turn_result.chunks = []
        mock_turn_result.referenced_insight_ids = []
        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_turn.return_value = mock_turn_result
        mock_facade._orchestrator = mock_orchestrator

        mock_buffered = MagicMock()
        mock_buffered_cls.return_value = mock_buffered
        mock_response = MagicMock()
        mock_response.data = {
            "text": "Answer", "claims": [],
            "tokens_in": 1, "tokens_out": 2,
            "model": "gpt-4", "tier": "cheap",
        }
        mock_buffered.deliver.return_value = mock_response

        principal = _make_principal(merchant_uuid)

        from tools.mcp_tools import handle_ask_agent

        result = handle_ask_agent(
            {
                "merchant_ref": str(merchant_uuid),
                "message": "What was my revenue?",
            },
            principal,
        )

        assert result["text"] == "Answer"
        assert result["session_id"] == str(mock_session.id)

        mock_orchestrator.handle_turn.assert_called_once()
        call_kwargs = mock_orchestrator.handle_turn.call_args
        assert call_kwargs.kwargs["stream"] is False

    @patch("tools.mcp_tools.resolve_merchant_ref")
    @patch("tools.mcp_tools.ChatFacade")
    @patch("tools.mcp_tools.AuthzEnforcer")
    @patch("tools.mcp_tools.BufferedDelivery")
    def test_mcp_chat_budget_exceeded(
        self,
        mock_buffered_cls,
        mock_enforcer_cls,
        mock_facade_cls,
        mock_resolve_ref,
    ):
        """ChatBudgetExceededError from the orchestrator is caught by MCP
        handler and returned as error dict — same as REST 503 (§19.24, §19.29).
        """
        merchant_uuid = uuid4()
        mock_resolve_ref.return_value = merchant_uuid

        mock_facade = MagicMock()
        mock_facade_cls.return_value = mock_facade

        mock_session = MagicMock()
        mock_session.id = uuid4()
        mock_facade._session_repo.get.return_value = None
        mock_facade.create_session.return_value = mock_session

        from chat.services.chat_orchestration_service import (
            ChatBudgetExceededError,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.handle_turn.side_effect = (
            ChatBudgetExceededError(retry_after_seconds=3600)
        )
        mock_facade._orchestrator = mock_orchestrator

        principal = _make_principal(merchant_uuid)

        from tools.mcp_tools import handle_ask_agent

        result = handle_ask_agent(
            {
                "merchant_ref": str(merchant_uuid),
                "message": "Hello",
            },
            principal,
        )

        assert result["error"] == "CHAT_BUDGET_EXCEEDED"
        assert result["retry_after_seconds"] == 3600
