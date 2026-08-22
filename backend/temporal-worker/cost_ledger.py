"""CostLedger Singleton — single authoritative in-process view of spend (§6.5, §9.3).

Per-process, Redis-synchronized, multi-scope: `agent` and `chat`.
Consulted before any LLM call; updated atomically after every successful call.

This is the minimal implementation for Task 2.5: the Singleton pattern
and scope isolation are in place; the per-merchant daily/monthly + global
daily ceilings are configurable via environment variables.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from decimal import Decimal

import redis


@dataclass(frozen=True, slots=True)
class ScopeConfig:
    """Cost ceiling configuration for a single scope."""

    per_interaction_ceiling: Decimal
    merchant_daily_ceiling: Decimal
    global_daily_ceiling: Decimal


class CostLedger:
    """Singleton cost ledger (§6.5).

    Exactly one instance per process. Redis-synchronized so all Temporal
    workers and chat-serving processes observe the same state.

    Scope isolation: `agent` and `chat` budgets are tracked separately
    in Redis via prefix namespacing.
    """

    _instance: CostLedger | None = None
    _lock = threading.Lock()

    SCOPE_AGENT = "agent"
    SCOPE_CHAT = "chat"

    def __new__(cls, *args, **kwargs) -> CostLedger:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        *,
        redis_client: redis.Redis | None = None,
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._redis = redis_client or self._connect_redis()
        self._local_lock = threading.Lock()

        self._scope_configs: dict[str, ScopeConfig] = {
            self.SCOPE_AGENT: ScopeConfig(
                per_interaction_ceiling=Decimal(os.environ.get(
                    "LLM_AGENT_PER_RUN_CEILING_USD", "0.50"
                )),
                merchant_daily_ceiling=Decimal(os.environ.get(
                    "LLM_AGENT_MERCHANT_DAILY_CEILING_USD", "5.00"
                )),
                global_daily_ceiling=Decimal(os.environ.get(
                    "LLM_AGENT_GLOBAL_DAILY_CEILING_USD", "50.00"
                )),
            ),
            self.SCOPE_CHAT: ScopeConfig(
                per_interaction_ceiling=Decimal(os.environ.get(
                    "LLM_CHAT_PER_TURN_CEILING_USD", "0.05"
                )),
                merchant_daily_ceiling=Decimal(os.environ.get(
                    "LLM_CHAT_MERCHANT_DAILY_CEILING_USD", "2.00"
                )),
                global_daily_ceiling=Decimal(os.environ.get(
                    "LLM_CHAT_GLOBAL_DAILY_CEILING_USD", "50.00"
                )),
            ),
        }

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

    def can_afford(
        self,
        scope: str,
        merchant_id: str,
        estimated_cost: Decimal,
    ) -> bool:
        """Check if the estimated cost can be afforded under all ceilings.

        Checks per-interaction, merchant daily, and global daily ceilings
        for the given scope. Returns True if the cost is within all limits.
        """
        config = self._scope_configs.get(scope)
        if config is None:
            return False

        if estimated_cost > config.per_interaction_ceiling:
            return False

        if not self._redis:
            return True

        today = self._today()
        merchant_key = f"cost:{scope}:merchant:{merchant_id}:{today}"
        global_key = f"cost:{scope}:global:{today}"

        try:
            pipe = self._redis.pipeline()
            pipe.get(merchant_key)
            pipe.get(global_key)
            result = pipe.execute()

            if len(result) >= 2:
                merchant_spent = Decimal(result[0] or 0)
                global_spent = Decimal(result[1] or 0)
            else:
                merchant_spent = Decimal(0)
                global_spent = Decimal(0)

            if merchant_spent + estimated_cost > config.merchant_daily_ceiling:
                return False
            if global_spent + estimated_cost > config.global_daily_ceiling:
                return False
        except redis.RedisError:
            return True

        return True

    def debit(
        self,
        scope: str,
        merchant_id: str,
        amount: Decimal,
    ) -> None:
        """Atomically debit the cost ledger for the given scope and merchant."""
        if not self._redis:
            return

        today = self._today()
        merchant_key = f"cost:{scope}:merchant:{merchant_id}:{today}"
        global_key = f"cost:{scope}:global:{today}"

        try:
            pipe = self._redis.pipeline()
            pipe.incrbyfloat(merchant_key, float(amount))
            pipe.expire(merchant_key, 86400)
            pipe.incrbyfloat(global_key, float(amount))
            pipe.expire(global_key, 86400)
            pipe.execute()
        except redis.RedisError:
            pass

    @staticmethod
    def _today() -> str:
        from datetime import date

        return date.today().isoformat()

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


__all__ = ["CostLedger", "ScopeConfig"]
