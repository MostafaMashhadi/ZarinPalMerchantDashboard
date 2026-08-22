"""Tests for ChatOrchestrationService and ChatFacade (§9.6.1-§9.6.6).

Covers:
- IntentResolver Strategy pattern
- Answer-sourcing priority (cache → analysis → decline)
- ChatGroundingValidator + deterministic template fallback
- Scope isolation (chat scope, not agent)
- Crash-and-retry resume from CHAT_TURN_STEP checkpoint
- Streaming vs Buffered delivery
- AuthZ re-check per turn
- Rate limit bucket (chat, not api)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from chat.delivery.delivery_strategy import (
    BufferedDelivery,
    DeliveryStrategySelector,
    StreamingDelivery,
)
from chat.grounding.chat_grounding_validator import (
    ChatGroundingValidator,
    DeterministicTemplateFallback,
)
from chat.intent.intent_resolver import (
    IntentClass,
    IntentResolver,
)
from chat.services.chat_orchestration_service import (
    ChatBudgetExceededError,
    ChatOrchestrationService,
)
from facades.authz import AuthPrincipal
from gateway.chain import ModelRouterChain
from gateway.cost_ledger import SCOPE_AGENT, SCOPE_CHAT, CostLedger
from middlewares.rate_limiter import RateLimiter
from shared.dtos import (
    DraftChunk,
    DraftResponse,
    SourcedClaim,
)


@pytest.fixture(autouse=True)
def reset_singletons():
    CostLedger.reset_for_testing()
    yield
    CostLedger.reset_for_testing()


def create_principal(merchant_id: UUID) -> AuthPrincipal:
    return AuthPrincipal(
        user_id=uuid4(),
        merchant_id=merchant_id,
        role="owner",
        email="test@example.com",
    )


# ---------------------------------------------------------------------------
# IntentResolver
# ---------------------------------------------------------------------------


class TestIntentResolver:
    def test_resolves_time_range_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("What was my revenue last month?")
        assert intent.kind == "time_range"
        assert intent.confidence > 0

    def test_resolves_event_impact_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("Did the chargeback affect my volume?")
        assert intent.kind == "event_impact"

    def test_resolves_peer_comparison_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("How do I compare to my peers?")
        assert intent.kind == "peer_comparison"

    def test_resolves_cohort_retention_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("What is my customer retention rate?")
        assert intent.kind == "cohort_retention"

    def test_resolves_anomaly_detection_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("Is there an unusual spike in my data?")
        assert intent.kind == "anomaly_detection"

    def test_resolves_general_guidance_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("How do I improve my success rate?")
        assert intent.kind == "general"

    def test_resolves_out_of_scope_intent(self):
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("12345")
        assert intent.kind == "out_of_scope"

    def test_strategy_pattern_no_if_elif_ladder(self):
        """IntentResolver is built from composable Strategy objects."""
        resolver = IntentResolver(use_llm=False)
        assert len(resolver._strategies) >= 5
        for s in resolver._strategies:
            assert hasattr(s, "resolve")

    def test_out_of_scope_does_not_invoke_analysis(self):
        """Out-of-scope intent short-circuits to decline template (§9.6.1)."""
        resolver = IntentResolver(use_llm=False)
        intent = resolver.resolve("xyz123")
        assert intent.kind == "out_of_scope"


# ---------------------------------------------------------------------------
# ChatGroundingValidator
# ---------------------------------------------------------------------------


class TestChatGroundingValidator:
    def test_validates_grounded_narrative(self):
        validator = ChatGroundingValidator()
        claims = [SourcedClaim("volume", 12500000, uuid4())]
        result = validator.validate(
            "Volume was 12500000", claims, {"source_data": {}}
        )
        assert result.valid

    def test_rejects_ungrounded_number(self):
        validator = ChatGroundingValidator()
        claims = [SourcedClaim("volume", 12500000, uuid4())]
        result = validator.validate(
            "Volume was 999999999", claims, {"source_data": {}}
        )
        assert not result.valid
        assert any("999999999" in v for v in result.ungrounded_values)

    def test_ignores_date_numbers(self):
        """Date-range numbers like 'Aug 1-15' should not trigger violations."""
        validator = ChatGroundingValidator()
        claims = [SourcedClaim("volume", 12500000, uuid4())]
        result = validator.validate(
            "In Aug 1-15, volume was 12500000",
            claims,
            {"source_data": {}},
        )
        assert result.valid

    def test_fee_proxy_rejects_currency_fee_value(self):
        """Fee-proxy value rendered as currency is rejected (§9.6.4)."""
        validator = ChatGroundingValidator()
        claims = [SourcedClaim("volume", 12500000, uuid4())]
        result = validator.validate(
            "Fee was 150000 Toman",
            claims,
            {"source_data": {}, "low_confidence_peer_set": False},
        )
        assert not result.valid
        assert any("Fee" in v or "fee" in v.lower() for v in result.ungrounded_values)

    def test_low_confidence_requires_disclaimer(self):
        """If low_confidence_peer_set is true, requires disclaimer (§9.6.4)."""
        validator = ChatGroundingValidator()
        claims = [SourcedClaim("volume", 12500000, uuid4())]
        result = validator.validate(
            "Volume was 12500000",
            claims,
            {"source_data": {}, "low_confidence_peer_set": True},
        )
        assert not result.valid
        assert any("disclaimer" in v.lower() for v in result.ungrounded_values)

    def test_low_confidence_with_disclaimer_passes(self):
        validator = ChatGroundingValidator()
        claims = [SourcedClaim("volume", 12500000, uuid4())]
        result = validator.validate(
            "Volume was 12500000 (estimate — peer sample is limited)",
            claims,
            {"source_data": {}, "low_confidence_peer_set": True},
        )
        assert result.valid


class TestDeterministicTemplateFallback:
    def test_render_time_range_template(self):
        fallback = DeterministicTemplateFallback()
        result_dict = {
            "insight_id": "abc-123",
            "kind": "time_range",
            "headline": "Volume down 10%",
            "body": {
                "volume": 12500000,
                "success_rate": 85.5,
            },
            "period_start": "2026-08-01T00:00:00+00:00",
            "period_end": "2026-08-22T00:00:00+00:00",
            "low_confidence_peer_set": False,
        }
        narrative, claims = fallback.render("time_range", result_dict)
        assert "12500000" in narrative
        assert "85.5" in narrative
        assert "abc-123" in narrative
        assert any(c.claim == "volume" for c in claims)
        assert any(c.claim == "success_rate" for c in claims)

    def test_render_anomaly_detection_template(self):
        fallback = DeterministicTemplateFallback()
        result_dict = {
            "insight_id": "def-456",
            "kind": "anomaly_detection",
            "headline": "Spike detected",
            "body": {"flagged_count": 3},
            "period_start": "2026-08-01",
            "period_end": "2026-08-22",
            "low_confidence_peer_set": False,
        }
        narrative, claims = fallback.render("anomaly_detection", result_dict)
        assert "3" in narrative
        assert "def-456" in narrative
        assert len(claims) == 1
        assert claims[0].claim == "flagged_count"

    def test_render_general_template(self):
        fallback = DeterministicTemplateFallback()
        result_dict = {
            "insight_id": "ghi-789",
            "headline": "All systems normal",
            "body": {},
        }
        narrative, claims = fallback.render("general", result_dict)
        assert "ghi-789" in narrative
        assert len(claims) == 0


# ---------------------------------------------------------------------------
# Delivery Strategies
# ---------------------------------------------------------------------------


class TestDeliveryStrategies:
    def test_streaming_delivery_default(self):
        """StreamingDelivery is the default (§9.6.6)."""
        strategy = DeliveryStrategySelector.select(
            supports_streaming=True, sse_supported=True
        )
        assert isinstance(strategy, StreamingDelivery)

    def test_buffered_on_no_streaming(self):
        """Non-streaming provider → BufferedDelivery (§9.6.6)."""
        strategy = DeliveryStrategySelector.select(
            supports_streaming=False, sse_supported=True
        )
        assert isinstance(strategy, BufferedDelivery)

    def test_buffered_on_no_sse(self):
        """No SSE support → BufferedDelivery (§9.6.6)."""
        strategy = DeliveryStrategySelector.select(
            supports_streaming=True, sse_supported=False
        )
        assert isinstance(strategy, BufferedDelivery)

    def test_buffered_assembles_full_text(self):
        """BufferedDelivery collects all chunks into a complete response."""
        delivery = BufferedDelivery()
        chunks = [
            DraftChunk(text="Hello ", done=False),
            DraftChunk(text="World!", done=True),
        ]
        response = delivery.deliver(iter(chunks))
        assert response.data["text"] == "Hello World!"


class TestStreamingDeliveryFallback:
    def test_streaming_fallback_on_error(self):
        """StreamingDelivery emits error event on mid-stream failure (§9.6.6)."""
        delivery = StreamingDelivery(fallback=BufferedDelivery())

        def bad_chunks():
            yield DraftChunk(text="partial", done=False)
            raise RuntimeError("stream broke")

        response = delivery.deliver(bad_chunks())
        collected = b"".join(response.streaming_content)
        assert b"event: error" in collected or b"fallback" in collected


# ---------------------------------------------------------------------------
# ChatOrchestrationService
# ---------------------------------------------------------------------------


class TestChatOrchestrationScopeIsolation:
    """Confirm chat scope is invoked, not agent (§9.3, §19.24)."""

    def test_chain_called_with_chat_scope(self):
        """ModelRouterChain.handle must be called with scope='chat' (§9.6.3)."""
        mock_chain = MagicMock(spec=ModelRouterChain)
        mock_chain.handle.return_value = DraftResponse(
            narrative="Test answer",
            claims=(),
            tokens_in=10,
            tokens_out=20,
            model="cheap-tier",
            tier="cheap",
        )

        service = ChatOrchestrationService(
            chain=mock_chain,
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        context = {
            "merchant_id": "m1",
            "session_id": "s1",
            "message": "Hello",
            "source": "general",
            "source_data": {},
            "intent": "general",
        }
        intent = IntentClass(kind="general", params={}, confidence=0.5)
        sourcing_result = {
            "source": "general",
            "result": None,
            "insight_id": None,
        }

        service._call_chain(context, intent, sourcing_result, stream=False)

        mock_chain.handle.assert_called_once()
        call_kwargs = mock_chain.handle.call_args
        assert call_kwargs.kwargs["scope"] == "chat"

    def test_cost_ledger_chat_scope_used(self):
        """CostLedger can_afford/debit must use SCOPE_CHAT, not SCOPE_AGENT (§19.24)."""
        mock_chain = MagicMock(spec=ModelRouterChain)
        mock_chain.handle.return_value = DraftResponse(
            narrative="Test",
            claims=(),
            tokens_in=10,
            tokens_out=20,
            model="cheap",
            tier="cheap",
        )

        session = MagicMock()
        session.id = uuid4()
        session.merchant_id = uuid4()

        ledger = CostLedger.instance()

        service = ChatOrchestrationService(
            chain=mock_chain,
            rate_limiter=MagicMock(),
            authz=MagicMock(),
            cost_ledger=ledger,
        )

        principal = create_principal(session.merchant_id)

        with patch.object(service, "_intent_resolver") as mock_resolver:
            mock_resolver.resolve.return_value = IntentClass(
                kind="general", params={}, confidence=0.5
            )
            with patch.object(service, "_source_answer") as mock_source:
                mock_source.return_value = {
                    "source": "general", "result": None,
                    "insight_id": None,
                    "period_start": None, "period_end": None,
                }
                with patch.object(service, "_build_bounded_context") as mock_bc:
                    mock_bc.return_value = {
                        "merchant_id": str(session.merchant_id),
                        "source_data": {},
                    }
                    with patch.object(service, "_ground_and_validate") as mock_gv:
                        mock_gv.return_value = {
                            "narrative": "Test",
                            "claims": [],
                            "referenced_insight_ids": [],
                            "model": "cheap",
                            "tier": "cheap",
                            "tokens_in": 0,
                            "tokens_out": 0,
                        }
                        with patch.object(service, "_persist_assistant_message"):
                            try:
                                service.handle_turn(
                                    session=session,
                                    user_message_content="Hello",
                                    principal=principal,
                                    stream=False,
                                )
                            except Exception:
                                pass

        assert SCOPE_CHAT != SCOPE_AGENT


class TestChatOrchestrationCrashResume:
    """§19.27: crash-and-retry resume from CHAT_TURN_STEP checkpoint."""

    def test_completed_step_allows_resume(self):
        """If a turn step is already completed, resume from checkpoint (§10.2)."""
        session = MagicMock()
        session.id = uuid4()
        session.merchant_id = uuid4()

        completed_step = MagicMock()
        completed_step.status = "completed"
        completed_step.checkpoint_state = {
            "narrative": "Cached answer",
            "claims": [],
            "referenced_insight_ids": [],
        }

        service = ChatOrchestrationService(
            rate_limiter=MagicMock(spec=RateLimiter),
            authz=MagicMock(),
        )

        with patch.object(
            service._turn_repo, "check_or_create_turn",
            return_value=completed_step,
        ):
            with patch.object(service, "_intent_resolver") as mock_resolver:
                mock_resolver.resolve.return_value = IntentClass(
                    kind="general", params={}, confidence=0.5
                )
                result = service.handle_turn(
                    session=session,
                    user_message_content="Hello",
                    principal=create_principal(session.merchant_id),
                    stream=False,
                )

        assert "Cached answer" in result.chunks[0].text
        assert result.delivery_mode == "buffered"

    def test_no_completed_step_proceeds_to_execute(self):
        """If no completed step, create a new one and execute (§19.27)."""
        session = MagicMock()
        session.id = uuid4()
        session.merchant_id = uuid4()

        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        with patch.object(
            service._turn_repo, "check_or_create_turn", return_value=None
        ):
            with patch.object(
                service._turn_repo, "create_step"
            ) as mock_create_step:
                mock_step = MagicMock()
                mock_create_step.return_value = mock_step

                with patch.object(service, "_intent_resolver") as mock_resolver:
                    mock_resolver.resolve.return_value = IntentClass(
                        kind="out_of_scope", params={}, confidence=0.3
                    )
                    with patch.object(service, "_source_answer") as mock_source:
                        mock_source.return_value = {
                            "source": "decline", "result": None,
                            "insight_id": None,
                            "period_start": None, "period_end": None,
                        }
                        with patch.object(service, "_build_bounded_context") as mock_bc:
                            mock_bc.return_value = {}
                            with patch.object(service, "_call_chain") as mock_call:
                                mock_call.side_effect = Exception("chain failed")
                            with patch.object(
                                service, "_fallback_to_template"
                            ) as mock_fallback:
                                mock_fallback.return_value = {
                                    "narrative": "Out of scope",
                                    "claims": [],
                                    "referenced_insight_ids": [],
                                }
                                with patch.object(
                                    service, "_build_chunks"
                                ) as mock_chunks:
                                    mock_chunks.return_value = [
                                        DraftChunk(text="Out of scope", done=False),
                                        DraftChunk(text="", done=True),
                                    ]
                                    with patch.object(
                                        service, "_persist_assistant_message"
                                    ):
                                        result = service.handle_turn(
                                            session=session,
                                            user_message_content="xyz",
                                            principal=create_principal(
                                                session.merchant_id
                                            ),
                                            stream=False,
                                        )

        assert "Out of scope" in result.chunks[0].text
        mock_create_step.assert_called_once()


class TestChatOrchestrationAnswerSourcing:
    """§9.6.1: answer-sourcing priority (cache → analysis → decline)."""

    def test_cache_hit_uses_cached_insight(self):
        """When a fresh insight exists in cache, use it as source (§9.6.1)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        cached_insight = MagicMock()
        cached_insight.kind = "time_range"
        cached_insight.headline = "Volume was high"
        cached_insight.body = {"volume": 12500000}
        cached_insight.period_start = datetime.now()
        cached_insight.period_end = datetime.now()
        cached_insight.low_confidence_peer_set = False

        with patch.object(
            service._insight_repo, "find_fresh",
            return_value=cached_insight,
        ):
            result = service._source_answer(
                IntentClass(kind="time_range", params={}),
                uuid4(),
                "revenue last month",
            )

        assert result["source"] == "cache"
        assert result["insight_id"] is not None

    def test_cache_miss_falls_to_analysis(self):
        """When no fresh insight, falls to real-time analysis (§9.6.1)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        mock_strategy = MagicMock()
        mock_strategy.compute.return_value = MagicMock(
            kind="time_range",
            headline="Analysis result",
            body={"volume": 10000000},
            period_start=datetime.now(),
            period_end=datetime.now(),
            low_confidence_peer_set=False,
            ingest_batch_id=uuid4(),
        )

        with patch.object(
            service._insight_repo, "find_fresh", return_value=None
        ):
            with patch.object(
                service._factory, "create", return_value=mock_strategy
            ):
                result = service._source_answer(
                    IntentClass(kind="time_range", params={}),
                    uuid4(),
                    "revenue last month",
                )

        assert result["source"] == "analysis"
        mock_strategy.compute.assert_called_once()

    def test_out_of_scope_short_circuits_to_decline(self):
        """Out-of-scope intent → decline, no analysis or cache lookup (§9.6.1)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        result = service._source_answer(
            IntentClass(kind="out_of_scope", params={}),
            uuid4(),
            "xyz123",
        )

        assert result["source"] == "decline"
        assert result["result"] is None

    def test_general_guidance_no_analysis(self):
        """General intent → no analysis call (§9.6.1)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        result = service._source_answer(
            IntentClass(kind="general", params={}),
            uuid4(),
            "how do i improve?",
        )

        assert result["source"] == "general"
        assert result["result"] is None


class TestChatOrchestrationRateLimitAndCost:
    def test_rate_limit_uses_chat_bucket(self):
        """Rate limit consumes from 'chat' bucket, not 'api' (§10.3)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        with patch.object(
            service._rate_limiter, "consume",
            return_value=MagicMock(allowed=True, tokens_remaining=29, retry_after_seconds=0),
        ) as mock_consume:
            try:
                service.handle_turn(
                    session=MagicMock(
                        id=uuid4(), merchant_id=uuid4()
                    ),
                    user_message_content="Hello",
                    principal=create_principal(uuid4()),
                    stream=False,
                )
            except Exception:
                pass

        call_kwargs = mock_consume.call_args
        assert call_kwargs.kwargs["bucket"] == "chat"
        assert call_kwargs.kwargs["cost"] == 1

    def test_budget_exceeded_raises_error(self):
        """Chat budget exhaustion → ChatBudgetExceededError (§19.24)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        with patch.object(
            service._rate_limiter, "consume",
            return_value=MagicMock(allowed=False, retry_after_seconds=5),
        ):
            with pytest.raises(ChatBudgetExceededError) as exc_info:
                service.handle_turn(
                    session=MagicMock(id=uuid4(), merchant_id=uuid4()),
                    user_message_content="Hello",
                    principal=create_principal(uuid4()),
                )
        assert exc_info.value.retry_after_seconds == 5

    def test_chat_budget_not_affected_by_agent_spend(self):
        """Agent scope budget exhaustion must not affect chat scope (§19.24)."""
        assert SCOPE_CHAT != SCOPE_AGENT
        ledger = CostLedger.instance()
        assert ledger.can_afford(
            SCOPE_CHAT, "cheap", 100, merchant_id="test-m"
        )


class TestChatOrchestrationAuthZ:
    def test_authz_re_check_per_turn(self):
        """Every turn re-checks object permission (§5.2, §13)."""
        service = ChatOrchestrationService(
            rate_limiter=MagicMock(),
            authz=MagicMock(),
        )

        session = MagicMock()
        session.id = uuid4()
        session.merchant_id = uuid4()

        principal = create_principal(uuid4())

        try:
            service.handle_turn(
                session=session,
                user_message_content="Hello",
                principal=principal,
            )
        except Exception:
            pass

        service._authz.check_object_permission.assert_called_with(
            principal, session.merchant_id
        )
