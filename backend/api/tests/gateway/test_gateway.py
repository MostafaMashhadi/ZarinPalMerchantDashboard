"""Tests for the LLM Gateway: AvalAIAdapter, ModelRouterChain, CircuitBreaker, CostLedger, cache.

Covers:
- §19.17: AllProvidersExhausted path (all tiers degraded)
- §19.24: Cost ceiling exceeded for both agent and chat scopes
- Chain wiring: cheap -> mid -> premium
- Scope isolation: agent spend never affects chat budget
- Circuit breaker state machine
- Response cache key construction
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from gateway.adapters.avalai_adapter import (
    AvalAIAdapter,
    estimate_cost_usd,
    get_tier_config,
)
from gateway.cache import LLMResponseCache
from gateway.chain import ModelRouterChain, ModelTierHandler, build_default_chain
from gateway.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitState,
    LLMCircuitBreaker,
)
from gateway.cost_ledger import (
    AGENT_CEILINGS,
    CHAT_CEILINGS,
    SCOPE_AGENT,
    SCOPE_CHAT,
    CostLedger,
)
from gateway.event_bus import InsightEventBus, InsightPublishedEvent
from shared.dtos import DraftRequest, DraftResponse
from shared.exceptions import AllProvidersExhausted, ProviderError


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def mock_redis_no_data():
    mock = MagicMock()
    mock.get.return_value = None
    return mock


@pytest.fixture(autouse=True)
def reset_singletons():
    CostLedger.reset_for_testing()
    InsightEventBus.reset_for_testing()
    yield
    CostLedger.reset_for_testing()
    InsightEventBus.reset_for_testing()


# ---------------------------------------------------------------------------
# AvalAIAdapter
# ---------------------------------------------------------------------------


class TestAvalAIAdapter:
    def test_adapters_share_same_interface(self):
        """Both adapters implement LLMProviderAdapter protocol (§9.3)."""
        adapter = AvalAIAdapter()
        assert hasattr(adapter, "complete")
        assert hasattr(adapter, "stream")

    def test_get_tier_config_cheap(self):
        config = get_tier_config("cheap")
        assert config.tier == "cheap"

    def test_get_tier_config_mid(self):
        config = get_tier_config("mid")
        assert config.tier == "mid"

    def test_get_tier_config_premium(self):
        config = get_tier_config("premium")
        assert config.tier == "premium"

    def test_get_tier_config_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            get_tier_config("unknown")

    def test_estimate_cost_usd_cheap(self):
        cost = estimate_cost_usd("cheap", 1000)
        assert cost == 0.05

    def test_estimate_cost_usd_mid(self):
        cost = estimate_cost_usd("mid", 1000)
        assert cost == 0.125

    def test_estimate_cost_usd_premium(self):
        cost = estimate_cost_usd("premium", 1000)
        assert cost == 0.5

    def test_estimate_cost_usd_unknown_falls_back_to_cheap(self):
        cost = estimate_cost_usd("unknown", 1000)
        assert cost == 0.05


class TestAvalAIAdapterParse:
    """Test _parse_response — the response parsing logic (§9.3)."""

    def test_parse_response_returns_draft_response(self):
        adapter = AvalAIAdapter()
        raw = {
            "model": "cheap-tier",
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "narrative": "test narrative",
                            "claims": [],
                            "tier": "cheap",
                        })
                    }
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 30},
        }
        response = adapter._parse_response(raw)

        assert response.narrative == "test narrative"
        assert response.tier == "cheap"
        assert response.tokens_in == 50
        assert response.tokens_out == 30

    def test_parse_response_with_claims(self):
        adapter = AvalAIAdapter()
        raw = {
            "model": "cheap-tier",
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "narrative": "Your volume was 12500000",
                            "claims": [
                                {"claim": "volume", "value": 12500000,
                                 "source_insight_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
                            ],
                            "tier": "cheap",
                        })
                    }
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 30},
        }
        response = adapter._parse_response(raw)

        assert len(response.claims) == 1
        assert response.claims[0].claim == "volume"
        assert response.claims[0].value == 12500000
        assert str(response.claims[0].source_insight_id) == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    def test_complete_raises_provider_error(self):
        adapter = AvalAIAdapter(api_key="test", base_url="http://test")
        mock_client = MagicMock()
        mock_client.post.side_effect = ProviderError("connection error")
        adapter._client = mock_client
        request = DraftRequest(
            scope="agent",
            estimated_tokens=100,
            system_prompt="test",
            context={"tier": "cheap"},
        )
        with pytest.raises(ProviderError):
            import asyncio
            asyncio.run(adapter.complete(request))


class TestAvalAIAdapterStream:
    """Test stream() method (§9.6.6)."""

    def test_stream_yields_chunks(self):
        adapter = AvalAIAdapter()

        mock_http_resp = MagicMock()
        mock_http_resp.__enter__ = MagicMock(return_value=mock_http_resp)
        mock_http_resp.__exit__ = MagicMock(return_value=False)
        mock_http_resp.iter_lines.return_value = iter([
            'data: {"choices":[{"delta":{"content":"hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ])

        mock_client = MagicMock()
        mock_client.post.return_value = mock_http_resp
        adapter._client = mock_client

        request = DraftRequest(
            scope="chat",
            estimated_tokens=50,
            system_prompt="test",
            context={"tier": "cheap"},
            stream=True,
        )
        chunks = list(adapter.stream(request))

        assert len(chunks) >= 2
        assert any(c.text == "hello" for c in chunks)
        assert any(c.text == " world" for c in chunks)
        assert any(c.done for c in chunks)

    def test_stream_yields_draft_chunks(self):
        adapter = AvalAIAdapter()
        mock_client = MagicMock()
        mock_http_resp = MagicMock()
        mock_http_resp.__enter__ = MagicMock(return_value=mock_http_resp)
        mock_http_resp.__exit__ = MagicMock(return_value=False)
        mock_http_resp.iter_lines.return_value = iter([])
        mock_client.post.return_value = mock_http_resp
        adapter._client = mock_client

        request = DraftRequest(
            scope="chat",
            estimated_tokens=50,
            system_prompt="test",
            context={"tier": "cheap"},
            stream=True,
        )
        chunks = list(adapter.stream(request))
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# LLMCircuitBreaker
# ---------------------------------------------------------------------------


class TestLLMCircuitBreaker:
    def test_initial_state_is_closed(self, mock_redis):
        cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        assert cb.get_state() == CircuitState.CLOSED

    def test_allows_requests_when_closed(self, mock_redis):
        cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        assert cb.allow_request() is True

    def test_five_failures_trip_open(self):
        """5 consecutive failures within 60s trips open for 30s (§9.3)."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "state" in key:
                return CircuitState.OPEN.value
            elif "opened_at" in key:
                import time
                return str(time.time() - 5)
            return None

        mock_redis.get.side_effect = get_side_effect
        mock_redis.zcard.return_value = 5
        mock_redis.zremrangebyscore.return_value = 0
        mock_redis.zadd.return_value = None
        mock_redis.expire.return_value = None

        cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_no_failures_stays_closed(self, mock_redis):
        cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

    def test_open_transitions_to_half_open_after_cooldown(self):
        """After 30s cooldown, circuit allows single half-open probe (§9.3)."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "state" in key:
                return CircuitState.OPEN.value
            elif "opened_at" in key:
                import time
                return str(time.time() - 35)
            return None

        mock_redis.get.side_effect = get_side_effect
        cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)

        assert cb.get_state() == CircuitState.HALF_OPEN

    def test_success_after_half_open_closes_circuit(self, mock_redis):
        cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        cb.record_success()
        mock_redis.set.return_value = None
        cb.record_success()

    def test_per_tier_breaker_independence(self, mock_redis):
        """Each tier has its own circuit breaker (§9.3)."""
        cheap_cb = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        mid_cb = LLMCircuitBreaker("mid", redis_client=mock_redis)
        assert cheap_cb.tier != mid_cb.tier

    def test_fails_open_without_redis(self):
        """Without Redis, circuit defaults to closed (fail-open)."""
        cb = LLMCircuitBreaker("cheap", redis_client=None)
        assert cb.allow_request() is True

    def test_config_custom_thresholds(self):
        config = CircuitBreakerConfig(
            failure_threshold=3,
            failure_window_seconds=120,
            cooldown_seconds=60,
        )
        cb = LLMCircuitBreaker("cheap", config=config)
        assert cb._config.failure_threshold == 3


# ---------------------------------------------------------------------------
# ModelTierHandler / ModelRouterChain
# ---------------------------------------------------------------------------


class TestModelRouterChain:
    def test_chain_has_three_tiers(self):
        chain = ModelRouterChain()
        assert chain.chain.tier == "cheap"
        assert chain.chain.next_.tier == "mid"
        assert chain.chain.next_.next_.tier == "premium"
        assert chain.chain.next_.next_.next_ is None

    def test_cheap_to_mid_to_premium_order(self):
        """Chain wiring order = cost-ascending: cheap -> mid -> premium (§6.3)."""
        cheap_breaker = LLMCircuitBreaker("cheap", redis_client=MagicMock())
        mid_breaker = LLMCircuitBreaker("mid", redis_client=MagicMock())
        premium_breaker = LLMCircuitBreaker("premium", redis_client=MagicMock())

        chain = ModelRouterChain(
            cheap_adapter=AvalAIAdapter(),
            mid_adapter=AvalAIAdapter(),
            premium_adapter=AvalAIAdapter(),
            cheap_breaker=cheap_breaker,
            mid_breaker=mid_breaker,
            premium_breaker=premium_breaker,
        )
        tiers = []
        node = chain.chain
        while node is not None:
            tiers.append(node.tier)
            node = node.next_
        assert tiers == ["cheap", "mid", "premium"]

    def test_scope_threaded_through_can_afford(self):
        """scope is passed to can_afford AND debit (§6.3)."""
        mock_ledger = MagicMock()
        mock_ledger.can_afford.return_value = False
        mock_ledger.debit = MagicMock()

        mock_adapter = MagicMock(spec=AvalAIAdapter)
        mock_breaker = MagicMock(spec=LLMCircuitBreaker)
        mock_breaker.allow_request.return_value = True

        handler = ModelTierHandler(
            "cheap", mock_adapter, mock_breaker, None
        )
        request = DraftRequest(
            scope="chat",
            estimated_tokens=100,
            system_prompt="test",
            context={"merchant_id": "m1"},
        )

        with pytest.raises(AllProvidersExhausted):
            handler.handle(request, mock_ledger, "chat")

        mock_ledger.can_afford.assert_called_once()
        call_args = mock_ledger.can_afford.call_args
        assert call_args.kwargs["scope"] == "chat"

    def test_scope_passed_to_debit_on_success(self):
        """On successful call, debit is called with the correct scope."""
        mock_ledger = MagicMock()
        mock_ledger.can_afford.return_value = True
        mock_ledger.debit = MagicMock()

        handler = ModelTierHandler(
            "cheap", MagicMock(spec=AvalAIAdapter), MagicMock(spec=LLMCircuitBreaker), None
        )
        handler.breaker.allow_request.return_value = True

        request = DraftRequest(
            scope="chat",
            estimated_tokens=100,
            system_prompt="test",
            context={"merchant_id": "m1"},
        )

        with patch.object(
            ModelTierHandler, "_complete"
        ) as mock_complete:
            mock_complete.return_value = DraftResponse(
                narrative="test",
                claims=(),
                tokens_in=10,
                tokens_out=20,
                model="cheap-tier",
                tier="cheap",
            )
            handler.handle(request, mock_ledger, "chat")

        mock_ledger.debit.assert_called_once()
        assert mock_ledger.debit.call_args.kwargs["scope"] == "chat"

    def test_same_chain_used_for_agent_and_chat(self):
        """The SAME chain instance is reused (§6.3)."""
        chain = build_default_chain()
        assert chain.chain.tier == "cheap"
        assert chain.chain.next_.tier == "mid"


class TestAllProvidersExhausted:
    """§19.17: all tiers degraded → AllProvidersExhausted"""

    def test_all_tiers_circuit_open_raises(self):
        """When all breakers are open, raise AllProvidersExhausted."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "state" in key:
                return CircuitState.OPEN.value
            elif "opened_at" in key:
                import time
                return str(time.time())
            return ""

        mock_redis.get.side_effect = get_side_effect
        mock_redis.exists.return_value = 0
        mock_redis.pipeline.return_value = MagicMock()

        cheap_breaker = LLMCircuitBreaker("cheap", redis_client=mock_redis)
        mid_breaker = LLMCircuitBreaker("mid", redis_client=mock_redis)
        premium_breaker = LLMCircuitBreaker("premium", redis_client=mock_redis)

        chain = ModelRouterChain(
            cheap_breaker=cheap_breaker,
            mid_breaker=mid_breaker,
            premium_breaker=premium_breaker,
        )

        mock_ledger = MagicMock()
        mock_ledger.can_afford.return_value = True

        request = DraftRequest(
            scope="agent",
            estimated_tokens=100,
            system_prompt="test",
            context={"merchant_id": str(uuid4())},
        )

        with patch.object(ModelTierHandler, "_complete"):
            with pytest.raises(AllProvidersExhausted):
                chain.handle(request, ledger=mock_ledger, scope="agent")

    def test_provider_error_fails_over_to_next_tier(self):
        """When cheap tier raises ProviderError, chain falls to mid (§19.17)."""
        mock_ledger = MagicMock()
        mock_ledger.can_afford.return_value = True

        cheap_adapter = MagicMock(spec=AvalAIAdapter)
        cheap_adapter.complete.side_effect = ProviderError("Cheap provider down")
        mid_adapter = MagicMock(spec=AvalAIAdapter)
        mid_adapter.complete.return_value = DraftResponse(
            narrative="mid response",
            claims=(),
            tokens_in=10,
            tokens_out=20,
            model="mid-tier",
            tier="mid",
        )
        premium_adapter = MagicMock(spec=AvalAIAdapter)
        premium_adapter.complete.return_value = DraftResponse(
            narrative="premium response",
            claims=(),
            tokens_in=10,
            tokens_out=20,
            model="premium-tier",
            tier="premium",
        )

        chain = ModelRouterChain(
            cheap_adapter=cheap_adapter,
            mid_adapter=mid_adapter,
            premium_adapter=premium_adapter,
            cheap_breaker=LLMCircuitBreaker("cheap", redis_client=MagicMock()),
            mid_breaker=LLMCircuitBreaker("mid", redis_client=MagicMock()),
            premium_breaker=LLMCircuitBreaker("premium", redis_client=MagicMock()),
        )

        request = DraftRequest(
            scope="agent",
            estimated_tokens=100,
            system_prompt="test",
            context={"merchant_id": str(uuid4())},
        )

        with patch.object(
            ModelTierHandler, "_complete"
        ) as mock_complete:
            mock_complete.side_effect = [
                ProviderError("Cheap failed"),
                DraftResponse(
                    narrative="mid",
                    claims=(),
                    tokens_in=10,
                    tokens_out=20,
                    model="mid-tier",
                    tier="mid",
                ),
            ]
            response = chain.handle(
                request, ledger=mock_ledger, scope="agent"
            )

        assert response.tier == "mid"


# ---------------------------------------------------------------------------
# CostLedger — §19.24: cost-ceiling-exceeded for BOTH scopes
# ---------------------------------------------------------------------------


class TestCostLedgerAgentScope:
    """§19.24: cost-ceiling-exceeded for the agent scope."""

    def test_agent_can_afford_within_per_interaction_ceiling(
        self, mock_redis_no_data
    ):
        ledger = CostLedger.instance(redis_client=mock_redis_no_data)
        assert ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=9999
        )

    def test_agent_exceeds_per_interaction_ceiling(
        self, mock_redis_no_data
    ):
        ledger = CostLedger.instance(redis_client=mock_redis_no_data)
        assert not ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=10001
        )

    def test_agent_exceeds_merchant_daily_ceiling(self):
        """Agent merchant daily cap is $5.00 (§6.5, §9.3)."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "agent:merchant:" in key:
                return "4.99"
            elif "agent:global:" in key:
                return None
            return None

        mock_redis.get.side_effect = get_side_effect
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert not ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=500
        )

    def test_agent_exceeds_global_daily_ceiling(self):
        """Agent global daily cap is $50.00 (§6.5, §9.3)."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = "50.0"
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert not ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=500
        )

    def test_agent_fails_open_without_redis(self):
        ledger = CostLedger.instance(redis_client=None)
        assert ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=100
        )

    def test_agent_debit_logs_correctly(self, mock_redis_no_data):
        ledger = CostLedger.instance(redis_client=mock_redis_no_data)

        with patch(
            "gateway.cost_ledger.CostLedger._log_to_postgres"
        ) as mock_log:
            ledger.debit(
                scope="agent",
                tier="cheap",
                tokens_in=100,
                tokens_out=200,
                merchant_id="m1",
                agent_run_step_id="a1b2c3d4",
            )
            mock_log.assert_called_once()
            call = mock_log.call_args
            assert call.kwargs["scope"] == "agent"
            assert call.kwargs["agent_run_step_id"] == "a1b2c3d4"

    def test_agent_debit_increments_redis_counter(self):
        mock_redis = MagicMock()
        mock_pipeline = MagicMock()
        mock_redis.pipeline.return_value = mock_pipeline
        ledger = CostLedger.instance(redis_client=mock_redis)

        with patch(
            "gateway.cost_ledger.CostLedger._log_to_postgres"
        ):
            ledger.debit(
                scope="agent",
                tier="cheap",
                tokens_in=100,
                tokens_out=200,
                merchant_id="m1",
            )

        mock_pipeline.incrbyfloat.assert_called()


class TestCostLedgerChatScope:
    """§19.24: cost-ceiling-exceeded for the chat scope."""

    def test_chat_can_afford_within_per_interaction_ceiling(
        self, mock_redis_no_data
    ):
        ledger = CostLedger.instance(redis_client=mock_redis_no_data)
        assert ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=999
        )

    def test_chat_exceeds_per_interaction_ceiling(
        self, mock_redis_no_data
    ):
        ledger = CostLedger.instance(redis_client=mock_redis_no_data)
        assert not ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=1001
        )

    def test_chat_exceeds_merchant_daily_ceiling(self):
        """Chat merchant daily cap is $2.00 (§6.5, §9.6.5)."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "chat:merchant:" in key:
                return "1.99"
            elif "chat:global:" in key:
                return None
            return None

        mock_redis.get.side_effect = get_side_effect
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert not ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=500
        )

    def test_chat_exceeds_global_daily_ceiling(self):
        """Chat global daily cap is $50.00 (§6.5, §9.6.5)."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = "50.0"
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert not ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=500
        )

    def test_chat_fails_open_without_redis(self):
        ledger = CostLedger.instance(redis_client=None)
        assert ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=100
        )

    def test_chat_debit_logs_correctly(self, mock_redis_no_data):
        ledger = CostLedger.instance(redis_client=mock_redis_no_data)

        with patch(
            "gateway.cost_ledger.CostLedger._log_to_postgres"
        ) as mock_log:
            ledger.debit(
                scope="chat",
                tier="cheap",
                tokens_in=100,
                tokens_out=200,
                merchant_id="m1",
                chat_turn_step_id="c1d2e3f4",
            )
            mock_log.assert_called_once()
            call = mock_log.call_args
            assert call.kwargs["scope"] == "chat"
            assert call.kwargs["chat_turn_step_id"] == "c1d2e3f4"


class TestCostLedgerScopeIsolation:
    """A chat ceiling breach must not be affected by agent spend and vice versa (§19.24)."""

    def test_chat_budget_breach_unaffected_by_agent_spend(self):
        """Agent has already spent its daily limit — chat budget is still
        independent (§9.6.5, §19.24)."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "agent:merchant:" in key:
                return "4.99"
            elif "agent:global:" in key:
                return None
            elif "chat:merchant:" in key:
                return None
            elif "chat:global:" in key:
                return None
            return None

        mock_redis.get.side_effect = get_side_effect
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert not ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=500
        )
        assert ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=500
        )

    def test_agent_budget_breach_unaffected_by_chat_spend(self):
        """Chat has already spent its daily limit — agent budget is still
        independent (§9.6.5, §19.24)."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "agent:merchant:" in key:
                return None
            elif "agent:global:" in key:
                return None
            elif "chat:merchant:" in key:
                return "1.99"
            elif "chat:global:" in key:
                return None
            return None

        mock_redis.get.side_effect = get_side_effect
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert not ledger.can_afford(
            scope="chat", tier="cheap", estimated_tokens=500
        )
        assert ledger.can_afford(
            scope="agent", tier="cheap", estimated_tokens=500
        )

    def test_chat_per_interaction_ceiling_lower_than_agent(self):
        """Chat has a lower per-interaction ceiling than agent (§9.6.5)."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        ledger = CostLedger.instance(redis_client=mock_redis)

        assert ledger.can_afford("agent", "cheap", 9999)
        assert not ledger.can_afford("chat", "cheap", 9999)

    def test_chat_global_daily_equal_to_agent_global_daily(self):
        """Both scopes have the same global daily cap ($50.00), but
        separate counters (§9.6.5, §6.5)."""
        assert AGENT_CEILINGS.global_daily == CHAT_CEILINGS.global_daily

    def test_chat_merchant_daily_lower_than_agent(self):
        """Chat has a lower merchant daily ceiling ($2.00 < $5.00) (§9.6.5)."""
        assert CHAT_CEILINGS.merchant_daily < AGENT_CEILINGS.merchant_daily

    def test_remaining_merchant_budget_isolated(self):
        """remaining_merchant_budget returns different values per scope."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "agent:merchant:" in key:
                return "1.00"
            return None

        mock_redis.get.side_effect = get_side_effect
        ledger = CostLedger.instance(redis_client=mock_redis)

        agent_remaining = ledger.remaining_merchant_budget(
            SCOPE_AGENT, "m1"
        )
        chat_remaining = ledger.remaining_merchant_budget(
            SCOPE_CHAT, "m1"
        )

        assert agent_remaining == Decimal("5.00") - Decimal("1.00")
        assert chat_remaining == Decimal("2.00")

    def test_remaining_global_budget_isolated(self):
        """remaining_global_budget returns different values per scope."""
        mock_redis = MagicMock()

        def get_side_effect(key):
            if "agent:global:" in key:
                return "10.0"
            return None

        mock_redis.get.side_effect = get_side_effect
        ledger = CostLedger.instance(redis_client=mock_redis)

        agent_remaining = ledger.remaining_global_budget(SCOPE_AGENT)
        chat_remaining = ledger.remaining_global_budget(SCOPE_CHAT)

        assert agent_remaining == Decimal("50.00") - Decimal("10.0")
        assert chat_remaining == Decimal("50.00")


# ---------------------------------------------------------------------------
# LLMResponseCache
# ---------------------------------------------------------------------------


class TestLLMResponseCache:
    def test_agent_cache_key_includes_ingest_batch_id(self):
        """Agentic cache key includes ingest_batch_id (§9.3)."""
        key1 = LLMResponseCache.agent_cache_key(
            merchant_id="m1",
            ingest_batch_id="batch-1",
            system_prompt="test prompt",
        )
        key2 = LLMResponseCache.agent_cache_key(
            merchant_id="m1",
            ingest_batch_id="batch-1",
            system_prompt="test prompt",
        )
        assert key1 == key2

    def test_different_ingest_batch_produces_different_key(self):
        key1 = LLMResponseCache.agent_cache_key(
            merchant_id="m1",
            ingest_batch_id="batch-1",
            system_prompt="test prompt",
        )
        key2 = LLMResponseCache.agent_cache_key(
            merchant_id="m1",
            ingest_batch_id="batch-2",
            system_prompt="test prompt",
        )
        assert key1 != key2

    def test_chat_cache_key_deterministic(self):
        """Chat cache key is deterministic for same inputs (§9.6.5)."""
        key1 = LLMResponseCache.chat_cache_key(
            merchant_id="m1",
            resolved_kind="peer_comparison",
            period_start="2026-01-01",
            period_end="2026-01-31",
            decile=5,
            category="retail",
        )
        key2 = LLMResponseCache.chat_cache_key(
            merchant_id="m1",
            resolved_kind="peer_comparison",
            period_start="2026-01-01",
            period_end="2026-01-31",
            decile=5,
            category="retail",
        )
        assert key1 == key2

    def test_chat_cache_key_different_params_produces_different_keys(self):
        key1 = LLMResponseCache.chat_cache_key(
            merchant_id="m1",
            resolved_kind="peer_comparison",
            period_start="2026-01-01",
            period_end="2026-01-31",
            decile=5,
        )
        key2 = LLMResponseCache.chat_cache_key(
            merchant_id="m1",
            resolved_kind="peer_comparison",
            period_start="2026-01-01",
            period_end="2026-01-31",
            decile=6,
        )
        assert key1 != key2

    def test_chat_cache_key_different_merchant_produces_different_key(self):
        key1 = LLMResponseCache.chat_cache_key(
            merchant_id="m1",
            resolved_kind="peer_comparison",
            period_start="2026-01-01",
            period_end="2026-01-31",
            decile=5,
        )
        key2 = LLMResponseCache.chat_cache_key(
            merchant_id="m2",
            resolved_kind="peer_comparison",
            period_start="2026-01-01",
            period_end="2026-01-31",
            decile=5,
        )
        assert key1 != key2

    def test_get_returns_none_without_redis(self):
        cache = LLMResponseCache(redis_client=None)
        assert cache.get("some-key") is None

    def test_get_returns_none_for_missing_key(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        cache = LLMResponseCache(redis_client=mock_redis)
        assert cache.get("missing-key") is None


# ---------------------------------------------------------------------------
# CostLedger Singleton
# ---------------------------------------------------------------------------


class TestCostLedgerSingleton:
    def test_singleton_returns_same_instance(self):
        a = CostLedger.instance()
        b = CostLedger.instance()
        assert a is b

    def test_reset_for_testing(self):
        a = CostLedger.instance()
        CostLedger.reset_for_testing()
        b = CostLedger.instance()
        assert a is not b


# ---------------------------------------------------------------------------
# InsightEventBus — verify it works as a subscriber pattern
# ---------------------------------------------------------------------------


class TestInsightEventBusObserver:
    def test_orchestrator_has_no_subscriber_knowledge(self):
        """The EventBus only knows about publish/subscribe — zero knowledge
        of who is listening (§6.4)."""
        bus = InsightEventBus.instance()

        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(handler)

        event = InsightPublishedEvent(
            insight_id=uuid4(),
            merchant_id=uuid4(),
            kind="anomaly_detection",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Test anomaly detected",
        )
        bus.publish(event)

        assert len(received) == 1
        assert received[0].kind == "anomaly_detection"
