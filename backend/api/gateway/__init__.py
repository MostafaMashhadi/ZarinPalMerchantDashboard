"""LLM Gateway — Adapter + Chain of Responsibility + Circuit Breaker + Singleton (§6.3, §9.3).

Four cooperating patterns:
1. Adapter (AvalAIAdapter) — provider wire format translation.
2. Chain of Responsibility (ModelRouterChain) — cheap → mid → premium failover.
3. Circuit Breaker (LLMCircuitBreaker) — per-tier, Redis-backed.
4. Singleton (CostLedger) — scope-aware spend tracking.
"""

from gateway.adapters.avalai_adapter import (
    AvalAIAdapter,
    AvalAITierConfig,
    TOKENS_PER_USD,
    estimate_cost_usd,
    get_tier_config,
)
from gateway.cache import LLMResponseCache
from gateway.circuit_breaker import (
    LLMCircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from gateway.chain import ModelRouterChain, ModelTierHandler, build_default_chain
from gateway.cost_ledger import (
    AGENT_CEILINGS,
    CHAT_CEILINGS,
    SCOPE_AGENT,
    SCOPE_CHAT,
    SCOPE_CONFIGS,
    ScopeCeilingConfig,
    CostLedger,
)

__all__ = [
    "AGENT_CEILINGS",
    "AvalAIAdapter",
    "AvalAITierConfig",
    "CHAT_CEILINGS",
    "CircuitBreakerConfig",
    "CircuitState",
    "CostLedger",
    "LLMResponseCache",
    "LLMCircuitBreaker",
    "SCOPE_AGENT",
    "SCOPE_CHAT",
    "SCOPE_CONFIGS",
    "ScopeCeilingConfig",
    "TOKENS_PER_USD",
    "estimate_cost_usd",
    "get_tier_config",
    "ModelRouterChain",
    "ModelTierHandler",
    "build_default_chain",
]
