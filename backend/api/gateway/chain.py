"""ModelTierHandler and ModelRouterChain — Chain of Responsibility (§6.3, §9.3).

Each handler independently checks its own LLMCircuitBreaker and consults the
CostLedger before attempting a call, then either serves the request or
passes it down the chain. The SAME chain instance is reused by both the
agentic Orchestrator (scope="agent") and the Chat Turn Orchestrator
(scope="chat") — only the scope argument differs.
"""

from __future__ import annotations

from typing import Protocol

from shared.dtos import DraftRequest, DraftResponse
from shared.exceptions import AllProvidersExhausted

from gateway.adapters.avalai_adapter import AvalAIAdapter
from gateway.circuit_breaker import LLMCircuitBreaker
from gateway.cost_ledger import CostLedger
from gateway.adapters.avalai_adapter import AvalAIAdapter, TOKENS_PER_USD
from gateway.circuit_breaker import LLMCircuitBreaker


class TierHandlerProtocol(Protocol):
    tier: str
    adapter: AvalAIAdapter
    breaker: LLMCircuitBreaker
    next_: object | None


class ModelTierHandler:
    """One link in the Chain of Responsibility (§6.3).

    Each tier decides locally whether it is allowed to serve
    (circuit closed/half-open AND under its own cost sub-ceiling
    FOR THE CALLING SCOPE) before either serving or delegating to next_.
    """

    def __init__(
        self,
        tier: str,
        adapter: AvalAIAdapter,
        breaker: LLMCircuitBreaker,
        next_: ModelTierHandler | None = None,
    ) -> None:
        self.tier = tier
        self.adapter = adapter
        self.breaker = breaker
        self.next_ = next_

    def handle(
        self,
        request: DraftRequest,
        ledger: CostLedger,
        scope: str,
    ) -> DraftResponse:
        """Handle a draft request, checking breaker + cost ledger (§6.3).

        Flow per spec pseudocode:
        1. If breaker allows AND ledger can afford → call adapter
        2. On success: record success, debit ledger, return response
        3. On ProviderError: record failure, fall through to next
        4. If next_ is None: raise AllProvidersExhausted
        5. Otherwise: delegate to next_.handle()
        """
        if self.breaker.allow_request() and self._can_afford(ledger, scope, request):
            try:
                response = self._complete(request)
                self.breaker.record_success()
                ledger.debit(
                    scope=scope,
                    tier=self.tier,
                    tokens_in=response.tokens_in,
                    tokens_out=response.tokens_out,
                    merchant_id=request.context.get("merchant_id", ""),
                    agent_run_step_id=request.context.get("agent_run_step_id"),
                    chat_turn_step_id=request.context.get("chat_turn_step_id"),
                )
                return response
            except Exception:
                self.breaker.record_failure()
                if self.next_ is None:
                    raise AllProvidersExhausted(
                        f"All providers exhausted at tier {self.tier}"
                    ) from None
                return self.next_.handle(request, ledger, scope)

        if self.next_ is None:
            raise AllProvidersExhausted(
                f"Circuit open or cost ceiling exceeded at all tiers"
            )
        return self.next_.handle(request, ledger, scope)

    def _can_afford(
        self, ledger: CostLedger, scope: str, request: DraftRequest
    ) -> bool:
        """Check cost budget for this tier and scope (§9.3)."""
        estimated_tokens = request.estimated_tokens or self._estimate_tokens(request)
        return ledger.can_afford(scope, self.tier, estimated_tokens)

    @staticmethod
    def _estimate_tokens(request: DraftRequest) -> int:
        """Rough token estimate from context size (§9.3)."""
        context_str = str(request.context)
        return max(len(context_str) // 4, 50)

    def _complete(self, request: DraftRequest) -> DraftResponse:
        """Execute the LLM call via the adapter."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.adapter.complete(request))


class ModelRouterChain:
    """Chain of Responsibility: cheap → mid → premium (§6.3, §9.3).

    Wiring order = cost-ascending: cheap -> mid -> premium.
    The SAME chain instance is reused by both the agentic Orchestrator
    (scope="agent") and the Chat Turn Orchestrator (scope="chat").
    """

    def __init__(
        self,
        cheap_adapter: AvalAIAdapter | None = None,
        mid_adapter: AvalAIAdapter | None = None,
        premium_adapter: AvalAIAdapter | None = None,
        cheap_breaker: LLMCircuitBreaker | None = None,
        mid_breaker: LLMCircuitBreaker | None = None,
        premium_breaker: LLMCircuitBreaker | None = None,
    ) -> None:
        self._cheap_adapter = cheap_adapter or AvalAIAdapter()
        self._mid_adapter = mid_adapter or AvalAIAdapter()
        self._premium_adapter = premium_adapter or AvalAIAdapter()
        self._cheap_breaker = cheap_breaker or LLMCircuitBreaker("cheap")
        self._mid_breaker = mid_breaker or LLMCircuitBreaker("mid")
        self._premium_breaker = premium_breaker or LLMCircuitBreaker("premium")

        self._chain = ModelTierHandler(
            "cheap",
            self._cheap_adapter,
            self._cheap_breaker,
            ModelTierHandler(
                "mid",
                self._mid_adapter,
                self._mid_breaker,
                ModelTierHandler(
                    "premium",
                    self._premium_adapter,
                    self._premium_breaker,
                    None,
                ),
            ),
        )

    @property
    def chain(self) -> ModelTierHandler:
        return self._chain

    def handle(
        self,
        request: DraftRequest,
        ledger: CostLedger | None = None,
        scope: str = "agent",
    ) -> DraftResponse:
        """Handle a request through the chain (§6.3).

        Args:
            request: Provider-agnostic draft request.
            ledger: CostLedger Singleton (defaults to instance()).
            scope: "agent" or "chat" — threaded through to can_afford/debit.
        """
        if ledger is None:
            ledger = CostLedger.instance()

        request = DraftRequest(
            scope=request.scope,
            estimated_tokens=request.estimated_tokens or 0,
            system_prompt=request.system_prompt,
            context={**request.context, "tier": "cheap"},
            stream=request.stream,
        )

        return self._chain.handle(request, ledger, scope)


def build_default_chain() -> ModelRouterChain:
    """Build the default chain with tier-specific breakers (§6.3)."""
    return ModelRouterChain(
        cheap_adapter=AvalAIAdapter(),
        mid_adapter=AvalAIAdapter(),
        premium_adapter=AvalAIAdapter(),
        cheap_breaker=LLMCircuitBreaker("cheap"),
        mid_breaker=LLMCircuitBreaker("mid"),
        premium_breaker=LLMCircuitBreaker("premium"),
    )


__all__ = ["ModelRouterChain", "ModelTierHandler", "build_default_chain"]
