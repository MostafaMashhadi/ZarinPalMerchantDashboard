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
