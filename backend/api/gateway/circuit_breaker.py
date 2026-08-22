"""LLMCircuitBreaker — per-tier circuit breaker, Redis-backed (§6.4, §9.3, §19.17).

State machine: closed to open (5 failures in 60s), open for 30s cooldown,
then half-open probe, then back to closed (success) or open (failure).

One instance per tier, shared across all Temporal workers and all API
processes handling chat turns.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from enum import Enum

import redis

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_FAILURE_WINDOW_SECONDS = 60
DEFAULT_COOLDOWN_SECONDS = 30


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    failure_window_seconds: int = DEFAULT_FAILURE_WINDOW_SECONDS
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS


class LLMCircuitBreaker:
    """Per-tier circuit breaker, Redis-backed (§6.4, §9.3).

    Shared across all processes and Temporal workers via Redis.
    Threshold: 5 consecutive failures within 60s trips open for 30s.
    """

    def __init__(
        self,
        tier: str,
        *,
        redis_client: redis.Redis | None = None,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._tier = tier
        self._config = config or CircuitBreakerConfig()
        self._redis = redis_client or self._connect_redis()
        self._key_prefix = f"circuit_breaker:{self._tier}"

    @property
    def tier(self) -> str:
        return self._tier

    def _connect_redis(self) -> redis.Redis | None:
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

    def _state_key(self) -> str:
        return f"{self._key_prefix}:state"

    def _failures_key(self) -> str:
        return f"{self._key_prefix}:failures"

    def _opened_at_key(self) -> str:
        return f"{self._key_prefix}:opened_at"

    def get_state(self) -> CircuitState:
        """Get current circuit state.

        - open: within cooldown window
        - half_open: cooldown elapsed, probe allowed
        - closed: normal operation
        """
        if not self._redis:
            return CircuitState.CLOSED

        try:
            state = self._redis.get(self._state_key())
            if state == CircuitState.OPEN.value:
                opened_at = self._redis.get(self._opened_at_key())
                if opened_at:
                    elapsed = time.time() - float(opened_at)
                    if elapsed >= self._config.cooldown_seconds:
                        return CircuitState.HALF_OPEN
                return CircuitState.OPEN
            return CircuitState.CLOSED
        except redis.RedisError:
            return CircuitState.CLOSED

    def allow_request(self) -> bool:
        """Whether a request should be allowed through the circuit (§9.3)."""
        state = self.get_state()
        if state == CircuitState.OPEN:
            return False
        return True

    def record_success(self) -> None:
        """Record a successful request — resets failure count (§19.17)."""
        if not self._redis:
            return

        try:
            pipe = self._redis.pipeline()
            pipe.set(self._state_key(), CircuitState.CLOSED.value)
            pipe.delete(self._failures_key())
            pipe.delete(self._opened_at_key())
            pipe.execute()
        except redis.RedisError:
            pass

    def record_failure(self) -> None:
        """Record a failed request — trips circuit if threshold reached (§9.3).

        Threshold: 5 consecutive failures within 60s → open for 30s.
        """
        if not self._redis:
            return

        try:
            now = time.time()
            window_start = now - self._config.failure_window_seconds

            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(self._failures_key(), 0, window_start)
            pipe.zcard(self._failures_key())
            pipe.zadd(self._failures_key(), {str(now): now})
            pipe.expire(self._failures_key(), self._config.failure_window_seconds)
            results = pipe.execute()

            failure_count = results[1] if len(results) >= 2 else 0

            if failure_count >= self._config.failure_threshold:
                pipe2 = self._redis.pipeline()
                pipe2.set(self._state_key(), CircuitState.OPEN.value)
                pipe2.set(self._opened_at_key(), str(now))
                pipe2.execute()
        except redis.RedisError:
            pass


__all__ = ["CircuitBreakerConfig", "CircuitState", "LLMCircuitBreaker"]
