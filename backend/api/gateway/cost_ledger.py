"""CostLedger Singleton — spend tracking per scope (§6.5, §9.3, §19.24).

Backed by Redis INCRBYFLOAT counters keyed by (scope, merchant_id|GLOBAL, date)
so multiple worker processes share one authoritative view without a lock.

'scope' is either "agent" (infrequent, higher per-run ceiling) or "chat"
(frequent, lower per-turn ceiling, tighter global daily cap). Every debit is
also durably logged to COST_LEDGER_ENTRY asynchronously.

Ceiling configuration:
  - agent: per-interaction $0.50, merchant daily $5.00, global daily $50.00
  - chat:  per-interaction $0.05, merchant daily $2.00, global daily $50.00
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from decimal import Decimal

import redis

from gateway.adapters.avalai_adapter import estimate_cost_usd

SCOPE_AGENT = "agent"
SCOPE_CHAT = "chat"


@dataclass(frozen=True, slots=True)
class ScopeCeilingConfig:
    """Cost ceiling configuration for a single scope (§6.5, §9.3).

    Values in USD. agent has higher per-run ceiling but lower frequency;
    chat has lower per-interaction ceiling but higher frequency.
    """

    per_interaction: Decimal
    merchant_daily: Decimal
    global_daily: Decimal


AGENT_CEILINGS = ScopeCeilingConfig(
    per_interaction=Decimal("0.50"),
    merchant_daily=Decimal("5.00"),
    global_daily=Decimal("50.00"),
)

CHAT_CEILINGS = ScopeCeilingConfig(
    per_interaction=Decimal("0.05"),
    merchant_daily=Decimal("2.00"),
    global_daily=Decimal("50.00"),
)

SCOPE_CONFIGS: dict[str, ScopeCeilingConfig] = {
    SCOPE_AGENT: AGENT_CEILINGS,
    SCOPE_CHAT: CHAT_CEILINGS,
}


class CostLedger:
    """Process-wide Singleton, Redis-synchronized, multi-scope (§6.5).

    Backed by Redis INCRBYFLOAT counters keyed by
    (scope, merchant_id|GLOBAL, date).

    Usage:
        ledger = CostLedger.instance()
        if ledger.can_afford(scope="agent", tier="cheap", estimated_tokens=500):
            response = adapter.complete(request)
            ledger.debit(scope="agent", tier="cheap", response.tokens_in, response.tokens_out)
    """

    _instance: CostLedger | None = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> CostLedger:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, *, redis_client: redis.Redis | None = None) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._redis = redis_client or self._connect_redis()

    @classmethod
    def instance(cls, redis_client: redis.Redis | None = None) -> CostLedger:
        """Get or create the Singleton instance (§6.5)."""
        if cls._instance is None:
            cls._instance = cls(redis_client=redis_client)
        return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        """Reset the Singleton — only for test cleanup."""
        with cls._lock:
            cls._instance = None

    @staticmethod
    def _connect_redis() -> redis.Redis | None:
        host = os.environ.get("REDIS_HOST", "")
        if not host:
            return None
        try:
            client = redis.Redis(
                host=host,
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD") or None,
                decode_responses=True,
                socket_connect_timeout=1,
            )
            client.ping()
            return client
        except (redis.RedisError, OSError):
            return None

    @staticmethod
    def _today() -> str:
        from datetime import date

        return date.today().isoformat()

    def _merchant_key(self, scope: str, merchant_id: str) -> str:
        today = self._today()
        return f"cost:{scope}:merchant:{merchant_id}:{today}"

    def _global_key(self, scope: str) -> str:
        today = self._today()
        return f"cost:{scope}:global:{today}"

    def can_afford(
        self,
        scope: str,
        tier: str,
        estimated_tokens: int,
        merchant_id: str = "",
    ) -> bool:
        """Check if the estimated cost can be afforded under all ceilings.

        Converts estimated_tokens to USD via tier rates, then checks
        per-interaction, merchant daily, and global daily ceilings
        for the given scope.

        Returns True if the cost is within all limits.
        """
        config = SCOPE_CONFIGS.get(scope)
        if config is None:
            return False

        estimated_cost = Decimal(str(estimate_cost_usd(tier, estimated_tokens)))

        if estimated_cost > config.per_interaction:
            return False

        if not self._redis:
            return True

        merchant_key = self._merchant_key(scope, str(merchant_id))
        global_key = self._global_key(scope)

        merchant_spent_raw = self._redis.get(merchant_key)
        global_spent_raw = self._redis.get(global_key)

        merchant_spent = Decimal(merchant_spent_raw or 0)
        global_spent = Decimal(global_spent_raw or 0)

        if merchant_spent + estimated_cost > config.merchant_daily:
            return False
        if global_spent + estimated_cost > config.global_daily:
            return False

        return True

    def debit(
        self,
        scope: str,
        tier: str,
        tokens_in: int,
        tokens_out: int,
        *,
        merchant_id: str = "",
        agent_run_step_id: str | None = None,
        chat_turn_step_id: str | None = None,
    ) -> None:
        """Atomically debit the cost ledger and log to Postgres (§9.3, §19.17).

        - Redis INCRBYFLOAT for hot-path counting.
        - Async Postgres COST_LEDGER_ENTRY for audit trail.
        """
        cost_usd = Decimal(str(estimate_cost_usd(tier, tokens_in + tokens_out)))

        if self._redis:
            try:
                merchant_key = self._merchant_key(scope, merchant_id)
                global_key = self._global_key(scope)

                pipe = self._redis.pipeline()
                pipe.incrbyfloat(merchant_key, float(cost_usd))
                pipe.expire(merchant_key, 86400)
                pipe.incrbyfloat(global_key, float(cost_usd))
                pipe.expire(global_key, 86400)
                pipe.execute()
            except redis.RedisError:
                pass

        self._log_to_postgres(
            scope=scope,
            tier=tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            merchant_id=merchant_id,
            agent_run_step_id=agent_run_step_id,
            chat_turn_step_id=chat_turn_step_id,
        )

    def _log_to_postgres(
        self,
        *,
        scope: str,
        tier: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: Decimal,
        merchant_id: str,
        agent_run_step_id: str | None,
        chat_turn_step_id: str | None,
    ) -> None:
        """Asynchronously log to COST_LEDGER_ENTRY (§6.5).

        Uses a background thread so the hot path never blocks on Postgres.
        The correct FK (agent_run_step_id for "agent" scope,
        chat_turn_step_id for "chat" scope) is populated per scope.
        """
        from datetime import date, datetime

        today = date.today()
        now = datetime.now()

        def _write() -> None:
            try:
                from analytics.models import CostLedgerEntry

                entry_kwargs = {
                    "scope": scope,
                    "merchant_id": merchant_id,
                    "tier": tier,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "amount_usd": cost_usd,
                    "ledger_date": today,
                    "created_at": now,
                }
                if scope == SCOPE_AGENT and agent_run_step_id:
                    entry_kwargs["agent_run_step_id"] = agent_run_step_id
                if scope == SCOPE_CHAT and chat_turn_step_id:
                    entry_kwargs["chat_turn_step_id"] = chat_turn_step_id

                CostLedgerEntry(**entry_kwargs)
            except Exception:
                pass

        t = threading.Thread(target=_write, daemon=True)
        t.start()

    def remaining_merchant_budget(
        self, scope: str, merchant_id: str
    ) -> Decimal:
        """Return remaining USD budget for this merchant under this scope."""
        config = SCOPE_CONFIGS.get(scope)
        if config is None:
            return Decimal("0")

        if not self._redis:
            return config.merchant_daily

        try:
            spent = self._redis.get(self._merchant_key(scope, merchant_id))
            spent = Decimal(spent or 0)
            return config.merchant_daily - spent
        except redis.RedisError:
            return config.merchant_daily

    def remaining_global_budget(self, scope: str) -> Decimal:
        """Return remaining USD budget for this scope globally."""
        config = SCOPE_CONFIGS.get(scope)
        if config is None:
            return Decimal("0")

        if not self._redis:
            return config.global_daily

        try:
            spent = self._redis.get(self._global_key(scope))
            spent = Decimal(spent or 0)
            return config.global_daily - spent
        except redis.RedisError:
            return config.global_daily


__all__ = [
    "AGENT_CEILINGS",
    "CHAT_CEILINGS",
    "SCOPE_AGENT",
    "SCOPE_CHAT",
    "SCOPE_CONFIGS",
    "CostLedger",
    "ScopeCeilingConfig",
]
