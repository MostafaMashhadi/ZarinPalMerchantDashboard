"""Tests for AuthZ enforcement and rate limiting (§13, §19.22, §19.23)."""

from datetime import UTC, datetime, timedelta
from typing import ClassVar
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from facades.authz import AuthPrincipal, AuthzEnforcer


@pytest.fixture
def merchant_id():
    return uuid4()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def principal(merchant_id, user_id):
    return AuthPrincipal(
        user_id=user_id,
        merchant_id=merchant_id,
        role="owner",
        email="owner@example.com",
    )


@pytest.fixture
def fixed_period():
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=30)
    return start, end


class TestAuthzEnforcer:
    def test_allows_principal_for_own_merchant(self, principal, merchant_id):
        enforcer = AuthzEnforcer()
        enforcer.check_object_permission(principal, merchant_id)

    def test_denies_anonymous_principal(self, merchant_id):
        enforcer = AuthzEnforcer()
        with pytest.raises(PermissionDenied):
            enforcer.check_object_permission(None, merchant_id)

    def test_denies_principal_for_other_merchant(self, principal):
        enforcer = AuthzEnforcer()
        other_merchant = uuid4()
        with pytest.raises(PermissionDenied):
            enforcer.check_object_permission(principal, other_merchant)

    def test_404_vs_403_distinction_merchant_not_found(self, principal, db):
        """§19.23: unresolvable merchant_ref → 404, handled by controller."""
        from controllers.analytics_controller import resolve_merchant_ref

        assert resolve_merchant_ref("nonexistent-key") is None

    def test_permission_denied_raised_on_mismatch(self, principal):
        """§19.23: resolvable merchant but AuthZ fails → 403."""
        enforcer = AuthzEnforcer()
        other_merchant = uuid4()
        with pytest.raises(PermissionDenied):
            enforcer.check_object_permission(principal, other_merchant)

    def test_permission_denied_raised_on_anonymous(self, merchant_id):
        enforcer = AuthzEnforcer()
        with pytest.raises(PermissionDenied):
            enforcer.check_object_permission(None, merchant_id)


class TestAnalyticsFacadeAuthZ:
    def test_dashboard_summary_requires_principal(self, merchant_id, fixed_period):
        from facades.analytics_facade import AnalyticsFacade

        start, end = fixed_period
        facade = AnalyticsFacade()

        with pytest.raises(PermissionDenied):
            facade.get_dashboard_summary(
                merchant_id=merchant_id,
                period_start=start,
                period_end=end,
                principal=None,
            )

    def test_run_analysis_requires_principal(self, merchant_id, fixed_period):
        from shared.dtos import AnalysisParams

        from facades.analytics_facade import AnalyticsFacade

        facade = AnalyticsFacade()
        start, end = fixed_period
        params = AnalysisParams(period_start=start, period_end=end)

        with pytest.raises(PermissionDenied):
            facade.run_analysis(
                merchant_id=merchant_id,
                kind="time_range",
                params=params,
                principal=None,
            )

    def test_dashboard_summary_denied_for_wrong_merchant(self, principal):
        from facades.analytics_facade import AnalyticsFacade

        facade = AnalyticsFacade()
        other_merchant = uuid4()

        with pytest.raises(PermissionDenied):
            facade.get_dashboard_summary(
                merchant_id=other_merchant,
                principal=principal,
            )


class TestRateLimiter:
    def test_rate_limiter_consume_allows_when_tokens_available(self):
        from middlewares.rate_limiter import RateLimitDecision, RateLimiter

        mock_redis = MagicMock()
        mock_redis.evalsha.return_value = [1, 59, 0]

        limiter = RateLimiter(redis_client=mock_redis)
        decision = limiter.consume(bucket="api", identity="user:123", cost=1)

        assert isinstance(decision, RateLimitDecision)
        assert decision.allowed is True
        assert decision.tokens_remaining == 59
        assert decision.retry_after_seconds == 0

    def test_rate_limiter_consume_denies_when_empty(self):
        from middlewares.rate_limiter import RateLimiter

        mock_redis = MagicMock()
        mock_redis.evalsha.return_value = [0, 0, 5]

        limiter = RateLimiter(redis_client=mock_redis)
        decision = limiter.consume(bucket="api", identity="user:123", cost=1)

        assert decision.allowed is False
        assert decision.retry_after_seconds == 5

    def test_rate_limiter_unknown_bucket_raises(self):
        from middlewares.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=MagicMock())
        with pytest.raises(ValueError, match="Unknown rate-limit bucket: unknown"):
            limiter.consume(bucket="unknown", identity="user:123", cost=1)

    def test_rate_limiter_fails_open_without_redis(self):
        from middlewares.rate_limiter import RateLimiter

        limiter = RateLimiter(redis_client=None)
        with patch.object(RateLimiter, "_get_redis", return_value=None):
            decision = limiter.consume(bucket="api", identity="user:123", cost=1)

        assert decision.allowed is True

    def test_api_bucket_config(self):
        from middlewares.rate_limiter import _BUCKET_CONFIGS

        config = _BUCKET_CONFIGS["api"]
        assert config.capacity == 60
        assert config.refill_rate == 1.0

    def test_chat_bucket_exists_for_sprint3(self):
        from middlewares.rate_limiter import _BUCKET_CONFIGS

        config = _BUCKET_CONFIGS["chat"]
        assert config.capacity == 30
        assert config.refill_rate == 0.5

    def test_trigger_summary_cost_is_5(self):
        from middlewares.rate_limiter import _endpoint_cost

        mock_request = MagicMock()
        mock_request.path_info = "/api/v1/merchants/M215/agent/trigger-summary"
        mock_request.method = "POST"
        cost = _endpoint_cost(mock_request)
        assert cost == 5

    def test_normal_endpoint_cost_is_1(self):
        from middlewares.rate_limiter import _endpoint_cost

        mock_request = MagicMock()
        mock_request.path_info = "/api/v1/merchants/M215/dashboard/summary"
        mock_request.method = "GET"
        cost = _endpoint_cost(mock_request)
        assert cost == 1


class TestRateLimitMiddleware:
    class _MockRequest:
        path_info: ClassVar[str] = "/api/v1/auth/login"
        method: ClassVar[str] = "POST"

        def __init__(self):
            self.META = {"REMOTE_ADDR": "127.0.0.1"}
            self.data = {}
            self.query_params = {}

    def test_429_contract_with_retry_after(self):
        import json

        from middlewares.rate_limiter import (
            RateLimitDecision,
            RateLimitMiddleware,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200

        middleware = RateLimitMiddleware(lambda req: mock_response)

        mock_limiter = MagicMock()
        mock_limiter.consume.return_value = RateLimitDecision(
            allowed=False,
            tokens_remaining=0,
            retry_after_seconds=5,
        )

        with patch.object(
            RateLimitMiddleware, "_get_limiter", return_value=mock_limiter
        ):
            response = middleware(self._MockRequest())

        assert response.status_code == 429
        assert response["Retry-After"] == "5"
        body = json.loads(response.content)
        assert body["error"] == "RATE_LIMITED"
        assert body["retry_after_seconds"] == 5

    def test_allows_request_when_tokens_available(self):
        from middlewares.rate_limiter import RateLimitDecision, RateLimitMiddleware

        mock_response = MagicMock()
        mock_response.status_code = 200

        middleware = RateLimitMiddleware(lambda req: mock_response)

        mock_limiter = MagicMock()
        mock_limiter.consume.return_value = RateLimitDecision(
            allowed=True,
            tokens_remaining=59,
            retry_after_seconds=0,
        )

        with patch.object(
            RateLimitMiddleware, "_get_limiter", return_value=mock_limiter
        ):
            response = middleware(self._MockRequest())

        assert response.status_code == 200
        mock_limiter.consume.assert_called_once()
