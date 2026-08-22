"""LLM Gateway — Adapter + Chain of Responsibility + Circuit Breaker + Singleton (§6.3, §9.3).

Four cooperating patterns:
1. Adapter (AvalAIAdapter) — provider wire format translation.
2. Chain of Responsibility (ModelRouterChain) — cheap → mid → premium failover.
3. Circuit Breaker (LLMCircuitBreaker) — per-tier, Redis-backed.
4. Singleton (CostLedger) — scope-aware spend tracking.
"""

from gateway.adapters.avalai_adapter import (
    TOKENS_PER_USD,
    AvalAIAdapter,
    AvalAITierConfig,
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
    SCOPE_CONFIGS,
    CostLedger,
    ScopeCeilingConfig,
)
from gateway.event_bus import (
    InsightEventBus,
    InsightPublishedEvent,
    Subscriber,
)
from gateway.notification_service import (
    MerchantNotificationPrefs,
    NotificationService,
)

__all__ = [
    "AGENT_CEILINGS",
    "CHAT_CEILINGS",
    "SCOPE_AGENT",
    "SCOPE_CHAT",
    "SCOPE_CONFIGS",
    "TOKENS_PER_USD",
    "AvalAIAdapter",
    "AvalAITierConfig",
    "CircuitBreakerConfig",
    "CircuitState",
    "CostLedger",
    "InsightEventBus",
    "InsightPublishedEvent",
    "LLMCircuitBreaker",
    "LLMResponseCache",
    "MerchantNotificationPrefs",
    "ModelRouterChain",
    "ModelTierHandler",
    "NotificationService",
    "ScopeCeilingConfig",
    "Subscriber",
    "build_default_chain",
    "estimate_cost_usd",
    "get_tier_config",
]
