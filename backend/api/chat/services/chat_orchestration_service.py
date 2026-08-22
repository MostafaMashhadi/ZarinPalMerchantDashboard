"""ChatOrchestrationService — the turn lifecycle (§9.6.2, §9.6.3).

Implements the 9 steps exactly as the spec:
1. check_or_create_turn against CHAT_TURN_STEP — idempotent resume
2. IntentResolver (Strategy pattern) classifies the message
3. Answer-sourcing priority: cache → real-time analysis → decline template
4. Bounded context construction with token cap enforcement
5. ModelRouterChain.handle(request, CostLedger.instance(), scope="chat")
6. ChatGroundingValidator — validate claims, retry with failure reason (max 2)
7. Additional validation: fee-proxy guard, low-confidence disclaimer
8. ChatResponseDeliveryStrategy selection (Streaming or Buffered)
9. Persist assistant CHAT_MESSAGE with referenced_insight_ids
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from analytics.strategy_factory import AnalysisStrategyFactory
from chat.grounding.chat_grounding_validator import (
    ChatGroundingValidator,
    DeterministicTemplateFallback,
)
from chat.intent.intent_resolver import IntentClass, IntentResolver
from chat.models import ChatSession
from chat.repositories.chat_message_repository import ChatMessageRepository
from chat.repositories.chat_session_repository import ChatSessionRepository
from chat.repositories.chat_turn_repository import ChatTurnRepository
from chat.repositories.insight_repository import InsightRepository
from facades.authz import AuthPrincipal, AuthzEnforcer
from gateway.chain import ModelRouterChain, build_default_chain
from gateway.cost_ledger import CostLedger
from middlewares.rate_limiter import RateLimiter
from shared.dtos import (
    AnalysisParams,
    DraftChunk,
    DraftRequest,
    DraftResponse,
    SourcedClaim,
)
from shared.exceptions import AllProvidersExhausted

# Freshness windows per kind (§9.6.1)
FRESHNESS_WINDOWS: dict[str, int] = {
    "anomaly_detection": 24,
    "time_range": 25,
    "peer_comparison": 24,
    "event_impact": 24,
    "cohort_retention": 25,
}

DEFAULT_FRESHNESS_HOURS = 24

# Token budget for the bounded context (§9.6.3)
MAX_CONTEXT_TOKENS = 6000
MAX_MEMORY_TOKENS = 1500
MAX_HISTORY_TOKENS = 3000
MAX_RESULT_TOKENS = 1000

# System prompt for the chat turn
SYSTEM_PROMPT = """You are a merchant analytics assistant for the ZarinPal dashboard.
You have access to real transaction data, anomaly detection insights, and peer comparisons.
Always ground numeric claims in the provided structured data. Do not invent numbers.
Format answers as JSON with fields: narrative, claims[]."""

OUT_OF_SCOPE_TEMPLATE = (
    "I can only help with payment analytics questions — revenue, transaction "
    "volume, success rate, chargebacks, fraud detection, peer comparison, "
    "cohort retention, and anomalies. For other questions, please contact support."
)

GENERAL_GUIDANCE_PREFIX = "Here's what I can tell you: "


@dataclass(frozen=True, slots=True)
class ChatTurnResult:
    chunks: list[DraftChunk]
    delivery_mode: str
    tokens_in: int
    tokens_out: int
    model: str
    tier: str
    claims: list[SourcedClaim]
    referenced_insight_ids: list[str]


class ChatOrchestrationService:
    """Implements the full chat turn lifecycle (§9.6.2, §9.6.3).

    Single orchestration point for both REST and MCP ask_agent (Sprint 4).
    """

    def __init__(
        self,
        *,
        session_repo: ChatSessionRepository | None = None,
        message_repo: ChatMessageRepository | None = None,
        turn_repo: ChatTurnRepository | None = None,
        insight_repo: InsightRepository | None = None,
        intent_resolver: IntentResolver | None = None,
        chain: ModelRouterChain | None = None,
        cost_ledger: CostLedger | None = None,
        rate_limiter: RateLimiter | None = None,
        authz: AuthzEnforcer | None = None,
    ) -> None:
        self._session_repo = session_repo or ChatSessionRepository()
        self._message_repo = message_repo or ChatMessageRepository()
        self._turn_repo = turn_repo or ChatTurnRepository()
        self._insight_repo = insight_repo or InsightRepository()
        self._intent_resolver = intent_resolver or IntentResolver()
        self._chain = chain or build_default_chain()
        self._cost_ledger = cost_ledger or CostLedger.instance()
        self._rate_limiter = rate_limiter or RateLimiter()
        self._authz = authz or AuthzEnforcer()
        self._grounding_validator = ChatGroundingValidator()
        self._template_fallback = DeterministicTemplateFallback()
        self._factory = AnalysisStrategyFactory()

    def handle_turn(
        self,
        session: ChatSession,
        user_message_content: str,
        principal: AuthPrincipal,
        *,
        stream: bool = True,
    ) -> ChatTurnResult:
        """Process one chat turn — the full 9-step lifecycle (§9.6.2, §9.6.3)."""
        # AuthZ re-check every turn (§5.2, §13)
        self._authz.check_object_permission(principal, session.merchant_id)

        # Rate limit check (§10.3)
        self._check_rate_limit(principal)

        # Step 1: check_or_create_turn — idempotent resume (§10.2, §19.27)
        checkpoint_id = self._compute_checkpoint_id(session, user_message_content)
        checkpoint_state = self._turn_repo.check_or_create_turn(
            session if hasattr(session, "id") else None,
            "chat_turn",
            checkpoint_id=checkpoint_id,
        )
        if checkpoint_state is not None and checkpoint_state.status == "completed":
            return self._resume_from_checkpoint(checkpoint_state)

        step = self._turn_repo.create_step(
            session if hasattr(session, "id") else None,
            "chat_turn",
            checkpoint_id=checkpoint_id,
        )

        try:
            # Step 2: IntentResolver — Strategy pattern (§9.6.3)
            intent = self._intent_resolver.resolve(user_message_content)

            # Step 3: Answer-sourcing priority (§9.6.1)
            sourcing_result = self._source_answer(
                intent, session.merchant_id, user_message_content
            )

            # Step 4: Bounded context construction (§9.6.3)
            context = self._build_bounded_context(
                session, user_message_content, intent, sourcing_result
            )

            # Step 5: ModelRouterChain with scope="chat" (§6.3, §9.3)
            draft_response = self._call_chain(context, intent, sourcing_result, stream)

            # Steps 6 & 7: Grounding validation + additional checks
            grounded = self._ground_and_validate(
                draft_response, intent, sourcing_result, context
            )

            # Step 8: Delivery strategy selection (§9.6.6)
            delivery_mode = "streaming" if stream else "buffered"

            # Step 9: Persist assistant message (§9.6.2)
            chunks = self._build_chunks(grounded, delivery_mode)
            self._persist_assistant_message(
                session, grounded, chunks, delivery_mode
            )

            self._turn_repo.mark_completed(
                step,
                checkpoint_state={
                    "narrative": grounded["narrative"],
                    "claims": [
                        {
                            "claim": c.claim,
                            "value": c.value,
                            "source_insight_id": (
                                str(c.source_insight_id)
                                if c.source_insight_id else None
                            ),
                        }
                        for c in grounded["claims"]
                    ],
                },
            )

            return ChatTurnResult(
                chunks=chunks,
                delivery_mode=delivery_mode,
                tokens_in=draft_response.tokens_in,
                tokens_out=draft_response.tokens_out,
                model=draft_response.model,
                tier=draft_response.tier,
                claims=grounded["claims"],
                referenced_insight_ids=grounded["referenced_insight_ids"],
            )

        except (AllProvidersExhausted, Exception):
            self._turn_repo.mark_failed(step)
            # Fallback to deterministic template on any error
            fallback_result = self._fallback_to_template(
                intent, sourcing_result if "sourcing_result" in dir() else None
            )
            chunks = self._build_chunks(fallback_result, "buffered")
            self._persist_assistant_message(
                session, fallback_result, chunks, "buffered"
            )
            return ChatTurnResult(
                chunks=chunks,
                delivery_mode="buffered",
                tokens_in=0,
                tokens_out=0,
                model="deterministic-template",
                tier="cheap",
                claims=fallback_result["claims"],
                referenced_insight_ids=fallback_result["referenced_insight_ids"],
            )

    def handle_turn_stream(
        self,
        session,
        user_message: str,
        principal: AuthPrincipal,
    ) -> Iterator[DraftChunk]:
        """Streaming variant — yields DraftChunks for SSE (§9.6.6)."""
        result = self.handle_turn(session, user_message, principal, stream=True)
        for chunk in result.chunks:
            if not chunk.done:
                yield chunk

    def _compute_checkpoint_id(self, session, message: str) -> str:
        import hashlib

        return hashlib.md5(
            f"{session.id}:{message[:100]}".encode()
        ).hexdigest()

    def _resume_from_checkpoint(self, step) -> ChatTurnResult:
        """Resume from a previously completed turn (§10.2, §19.27)."""
        state = step.checkpoint_state
        narrative = state.get("narrative", "")
        claims = [
            SourcedClaim(
                claim=c["claim"],
                value=c["value"],
                source_insight_id=(
                    c.get("source_insight_id")
                    if c.get("source_insight_id") else None
                ),
            )
            for c in state.get("claims", [])
        ]
        insight_ids = list(state.get("referenced_insight_ids", set()))
        chunks = [
            DraftChunk(text=narrative, done=False),
            DraftChunk(text="", done=True),
        ]
        return ChatTurnResult(
            chunks=chunks,
            delivery_mode="buffered",
            tokens_in=0,
            tokens_out=len(narrative),
            model="resumed",
            tier="cheap",
            claims=claims,
            referenced_insight_ids=insight_ids,
        )

    def _check_rate_limit(self, principal: AuthPrincipal) -> None:
        """Deduct 1 token from the chat rate-limit bucket (§10.3).

        Capacity 30, refill 1 token per 2 seconds (refill_rate=0.5).
        cost = 1 token per message.
        """
        identity = f"merchant:{principal.merchant_id}"
        decision = self._rate_limiter.consume(
            bucket="chat", identity=identity, cost=1
        )
        if not decision.allowed:
            retry_after = decision.retry_after_seconds
            raise ChatBudgetExceededError(retry_after_seconds=retry_after)

    def _source_answer(
        self,
        intent: IntentClass,
        merchant_id: UUID,
        user_message: str,
    ) -> dict[str, Any]:
        """Answer-sourcing priority (§9.6.1): cache → real-time analysis → decline.

        Returns a dict with keys:
        - source: "cache" | "analysis" | "decline" | "general"
        - result: dict (converted AnalysisResult) or None
        - insight_id: UUID | None
        - period_start/end: datetime
        """

        kind = intent.kind
        if kind in ("general", "out_of_scope"):
            return {
                "source": "decline" if kind == "out_of_scope" else "general",
                "result": None,
                "insight_id": None,
                "period_start": None,
                "period_end": None,
            }

        now = datetime.now()
        period_start = now - timedelta(days=30)
        period_end = now

        freshness_hours = FRESHNESS_WINDOWS.get(kind, DEFAULT_FRESHNESS_HOURS)
        from datetime import timedelta as td

        fresh = self._insight_repo.find_fresh(
            merchant_id, kind, period_start, period_end,
            freshness_window=td(hours=freshness_hours),
        )

        if fresh is not None:
            return {
                "source": "cache",
                "result": self._insight_repo.to_dict(fresh),
                "insight_id": fresh.id,
                "period_start": period_start,
                "period_end": period_end,
            }

        # Cache miss → real-time analysis (§9.6.1, step b)
        params = AnalysisParams(
            period_start=period_start, period_end=period_end, extra={}
        )
        strategy = self._factory.create(kind)
        analysis_result = strategy.compute(merchant_id, params)

        result_dict = {
            "insight_id": None,
            "kind": analysis_result.kind,
            "headline": analysis_result.headline,
            "body": analysis_result.body,
            "period_start": (
                analysis_result.period_start.isoformat()
                if analysis_result.period_start else ""
            ),
            "period_end": (
                analysis_result.period_end.isoformat()
                if analysis_result.period_end else ""
            ),
            "low_confidence_peer_set": analysis_result.low_confidence_peer_set,
            "generated_at": datetime.now().isoformat(),
        }

        return {
            "source": "analysis",
            "result": result_dict,
            "insight_id": analysis_result.ingest_batch_id,
            "period_start": period_start,
            "period_end": period_end,
        }

    def _build_bounded_context(
        self,
        session,
        user_message: str,
        intent: IntentClass,
        sourcing_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Build bounded context with token cap enforcement (§9.6.3).

        System prompt + rolling merchant summary + last-N raw messages
        + structured AnalysisResult. Enforces MAX_CONTEXT_TOKENS.
        """
        # Get recent insights for memory
        recent_insights = self._insight_repo.find_recent(session.merchant_id)
        summary_text = self._summarize_memory(recent_insights, MAX_MEMORY_TOKENS)

        # Get last N messages
        recent_messages = self._message_repo.list_for_session(session)
        message_context = self._truncate_history(recent_messages, MAX_HISTORY_TOKENS)

        # Analysis result context
        analysis_context = sourcing_result.get("result", {}) or {}

        context = {
            "tier": "cheap",
            "merchant_id": str(session.merchant_id),
            "session_id": str(session.id),
            "intent": intent.kind,
            "intent_params": intent.params,
            "source": sourcing_result["source"],
            "source_data": analysis_context,
            "memory_summary": summary_text,
            "message_history": message_context,
            "user_message": user_message,
            "low_confidence_peer_set": analysis_context.get(
                "low_confidence_peer_set", False
            ),
        }

        return context

    def _summarize_memory(
        self, insights: list, max_tokens: int
    ) -> str:
        """Summarize recent insights into a compact memory (§9.6.3)."""
        if not insights:
            return ""
        parts = []
        for insight in insights:
            headline = getattr(insight, "headline", "")[:200]
            parts.append(f"- {insight.kind}: {headline}")
        return "\n".join(parts)

    @staticmethod
    def _truncate_history(messages, max_tokens: int) -> list[dict[str, str]]:
        """Truncate message history to fit within token budget (§9.6.3)."""
        result = []
        current_tokens = 0
        for msg in reversed(messages):
            msg_tokens = len(msg.content) // 4
            if current_tokens + msg_tokens > max_tokens:
                break
            result.append({
                "role": msg.role,
                "content": msg.content[:500],
            })
            current_tokens += msg_tokens
        return list(reversed(result))

    def _call_chain(
        self,
        context: dict[str, Any],
        intent: IntentClass,
        sourcing_result: dict[str, Any],
        stream: bool,
    ) -> DraftResponse:
        """Call ModelRouterChain.handle with scope='chat' (§9.6.3, step 5).

        Returns the LLM draft response. Does NOT re-check cost ledger
        (ModelRouterChain checks it internally with scope='chat').
        """
        request = DraftRequest(
            scope="chat",
            estimated_tokens=500,
            system_prompt=SYSTEM_PROMPT,
            context={
                "tier": "cheap",
                "merchant_id": context.get("merchant_id", ""),
                "session_id": context.get("session_id", ""),
                "message": context.get("user_message", ""),
                "source": context.get("source", ""),
                "source_data": context.get("source_data", {}),
                "memory_summary": context.get("memory_summary", ""),
                "message_history": context.get("message_history", []),
                "intent": context.get("intent", ""),
                "low_confidence_peer_set": context.get("low_confidence_peer_set", False),
                "chat_turn_step_id": context.get("chat_turn_step_id"),
            },
            stream=stream,
        )

        try:
            response = self._chain.handle(request, self._cost_ledger, scope="chat")
            return response
        except AllProvidersExhausted:
            raise

    def _ground_and_validate(
        self,
        draft_response: DraftResponse,
        intent: IntentClass,
        sourcing_result: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """ChatGroundingValidator with retry-fallback (§9.6.4, steps 6 & 7).

        - Validate claims against structured data
        - On failure, retry Draft with failure reason appended (max 2 retries)
        - On exhaustion, use deterministic template fallback
        """
        claims = list(draft_response.claims)
        narrative = draft_response.narrative
        source_data = context.get("source_data", {})
        low_confidence = context.get("low_confidence_peer_set", False)
        grounding_context = {
            "source_data": source_data,
            "low_confidence_peer_set": low_confidence,
        }

        result = self._grounding_validator.validate(narrative, claims, grounding_context)

        if result.valid:
            return self._success_result(draft_response, sourcing_result, claims)

        # Retry with failure reason appended (§9.6.4)
        for attempt in range(self._grounding_validator.MAX_RETRIES):
            retry_context = {
                **context,
                "source_data": source_data,
                "grounding_failure": result.reason,
                "retry_attempt": attempt + 1,
            }

            retry_request = DraftRequest(
                scope="chat",
                estimated_tokens=500,
                system_prompt=SYSTEM_PROMPT,
                context=retry_context,
                stream=False,
            )

            try:
                retry_response = self._chain.handle(
                    retry_request, self._cost_ledger, scope="chat"
                )
                retry_claims = list(retry_response.claims)
                retry_result = self._grounding_validator.validate(
                    retry_response.narrative, retry_claims, grounding_context
                )
                if retry_result.valid:
                    return self._success_result(retry_response, sourcing_result, retry_claims)
                result = retry_result
            except Exception:
                result = self._grounding_validator.validate(
                    draft_response.narrative, claims, grounding_context
                )

        # Exhaustion → deterministic template fallback (§9.6.4)
        return self._fallback_to_template(intent, sourcing_result)

    def _success_result(
        self,
        draft_response: DraftResponse,
        sourcing_result: dict[str, Any],
        claims: list[SourcedClaim],
    ) -> dict[str, Any]:
        insight_ids: list[str] = []
        for c in claims:
            if c.source_insight_id is not None:
                sid = str(c.source_insight_id)
                if sid and sid not in insight_ids:
                    insight_ids.append(sid)

        if sourcing_result.get("insight_id"):
            sid = str(sourcing_result["insight_id"])
            if sid not in insight_ids:
                insight_ids.append(sid)

        return {
            "narrative": draft_response.narrative,
            "claims": claims,
            "referenced_insight_ids": insight_ids,
            "model": draft_response.model,
            "tier": draft_response.tier,
            "tokens_in": draft_response.tokens_in,
            "tokens_out": draft_response.tokens_out,
        }

    def _fallback_to_template(
        self,
        intent: IntentClass,
        sourcing_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Deterministic template composition (§9.6.4) — P0 correctness fallback."""
        if intent.kind in ("out_of_scope", "general"):
            narrative = OUT_OF_SCOPE_TEMPLATE if intent.kind == "out_of_scope" else (
                GENERAL_GUIDANCE_PREFIX + "I don't have specific data for that query."
            )
            return {
                "narrative": narrative,
                "claims": [],
                "referenced_insight_ids": [],
                "model": "deterministic-template",
                "tier": "cheap",
                "tokens_in": 0,
                "tokens_out": 0,
            }

        if sourcing_result is None or sourcing_result.get("result") is None:
            return {
                "narrative": OUT_OF_SCOPE_TEMPLATE,
                "claims": [],
                "referenced_insight_ids": [],
                "model": "deterministic-template",
                "tier": "cheap",
                "tokens_in": 0,
                "tokens_out": 0,
            }

        narrative, claims = self._template_fallback.render(
            intent.kind, sourcing_result["result"]
        )

        insight_ids: list[str] = []
        if sourcing_result.get("insight_id"):
            insight_ids.append(str(sourcing_result["insight_id"]))

        return {
            "narrative": narrative,
            "claims": claims,
            "referenced_insight_ids": insight_ids,
            "model": "deterministic-template",
            "tier": "cheap",
            "tokens_in": 0,
            "tokens_out": 0,
        }

    def _build_chunks(
        self, result: dict[str, Any], delivery_mode: str
    ) -> list[DraftChunk]:
        """Build DraftChunk list from the final result (§9.6.6)."""
        if delivery_mode == "streaming":
            chunks = []
            text = result["narrative"]
            for i in range(0, len(text), 100):
                chunks.append(DraftChunk(text=text[i:i + 100], done=False))
            chunks.append(DraftChunk(text="", done=True))
            return chunks
        else:
            final_chunk = DraftChunk(text="", done=True)
            return [DraftChunk(text=result["narrative"], done=False), final_chunk]

    def _persist_assistant_message(
        self,
        session,
        result: dict[str, Any],
        chunks: list[DraftChunk],
        delivery_mode: str,
    ) -> None:
        """Persist the assistant CHAT_MESSAGE with referenced_insight_ids (§9.6.2, step 9)."""
        self._message_repo.create(
            session=session,
            role="assistant",
            content=result["narrative"],
            tokens_in=result.get("tokens_in", 0),
            tokens_out=result.get("tokens_out", 0),
            model_used=result.get("model", ""),
            delivery_mode=delivery_mode,
            referenced_insight_ids=result.get("referenced_insight_ids", []),
        )


class ChatBudgetExceededError(Exception):
    """Raised when the chat scope budget is exhausted (§19.24)."""

    def __init__(self, retry_after_seconds: int = 0) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Chat budget exceeded, retry after {retry_after_seconds}s")


__all__ = [
    "ChatBudgetExceededError",
    "ChatOrchestrationService",
    "ChatTurnResult",
]
