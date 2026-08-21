from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, TypeVar

from ingestion.config import RedisConfig, default_redis_config

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Raised when query execution is rejected because the circuit breaker is open."""


class ClickHouseCircuitBreaker:
    """Circuit breaker for ClickHouse queries per spec §10.3 / §19.12.

    State machine: CLOSED -> OPEN (on 3 timeouts in 60s) -> HALF_OPEN (after 20s) -> CLOSED/OPEN.
    Falls back to Redis cache-aside with payload tagged "data_freshness": "cached_fallback".
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        failure_window_seconds: float = 60.0,
        recovery_timeout_seconds: float = 20.0,
        redis_config: RedisConfig | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.failure_window_seconds = failure_window_seconds
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.redis_config = redis_config or default_redis_config
        self._redis = redis_client
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._failure_timestamps: list[float] = []
        self._last_state_change: float = time.time()
        self._half_open_probe_in_flight: bool = False

    def _get_redis(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis

            self._redis = redis.Redis(
                host=self.redis_config.host,
                port=self.redis_config.port,
                password=self.redis_config.password or None,
                decode_responses=True,
            )
            return self._redis
        except Exception as e:
            logger.warning("Redis connection unavailable for circuit breaker: %s", e)
            return None

    @property
    def state(self) -> CircuitState:
        now = time.time()
        if self._state == CircuitState.OPEN:
            if now - self._last_state_change >= self.recovery_timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        logger.info("ClickHouseCircuitBreaker transitioning from %s to %s", self._state, new_state)
        self._state = new_state
        self._last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._failure_timestamps.clear()
            self._half_open_probe_in_flight = False
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_probe_in_flight = False

    def record_success(self) -> None:
        """Record a successful ClickHouse query."""
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)
        else:
            self._consecutive_failures = 0

    def record_failure(self, is_timeout: bool = True) -> None:
        """Record a ClickHouse timeout or severe failure."""
        now = time.time()
        # Clean expired timestamps outside the rolling window
        self._failure_timestamps = [ts for ts in self._failure_timestamps if now - ts <= self.failure_window_seconds]
        self._failure_timestamps.append(now)
        self._consecutive_failures += 1

        if self.state == CircuitState.HALF_OPEN:
            # Probe failed, reopen breaker
            self._transition_to(CircuitState.OPEN)
        elif len(self._failure_timestamps) >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def cache_result(self, cache_key: str, data: Any, ttl_seconds: int = 86400) -> None:
        """Store last-known-good summary in Redis cache-aside."""
        r = self._get_redis()
        if r is None:
            return
        try:
            payload = json.dumps(data, default=str)
            r.setex(f"rollup_summary_cache:{cache_key}", ttl_seconds, payload)
        except Exception as e:
            logger.warning("Failed to cache rollup summary in Redis: %s", e)

    def get_cached_fallback(self, cache_key: str) -> dict[str, Any] | None:
        """Retrieve last-known cached rollup summary and tag with data_freshness=cached_fallback."""
        r = self._get_redis()
        if r is None:
            return None
        try:
            raw = r.get(f"rollup_summary_cache:{cache_key}")
            if not raw:
                return None
            data = json.loads(raw)
            if isinstance(data, dict):
                data["data_freshness"] = "cached_fallback"
            return data
        except Exception as e:
            logger.warning("Failed to get cached rollup fallback from Redis: %s", e)
            return None

    def execute_with_fallback(
        self,
        query_fn: Callable[[], T],
        cache_key: str,
        fallback_fn: Callable[[], T] | None = None,
    ) -> tuple[T, bool]:
        """Execute query protected by circuit breaker.

        Returns (result, is_fallback).
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.warning("Circuit breaker OPEN. Using cached fallback for key '%s'", cache_key)
            fallback = self.get_cached_fallback(cache_key)
            if fallback is not None:
                return fallback, True  # type: ignore[return-value]
            if fallback_fn is not None:
                res = fallback_fn()
                if isinstance(res, dict):
                    res["data_freshness"] = "cached_fallback"
                return res, True
            raise CircuitBreakerOpenException("ClickHouse circuit breaker is OPEN and no fallback cached.")

        try:
            result = query_fn()
            self.record_success()
            # Cache the successful result for future fallback
            self.cache_result(cache_key, result)
            return result, False
        except Exception as e:
            logger.error("ClickHouse query execution failed: %s", e)
            self.record_failure(is_timeout=True)
            fallback = self.get_cached_fallback(cache_key)
            if fallback is not None:
                return fallback, True  # type: ignore[return-value]
            if fallback_fn is not None:
                res = fallback_fn()
                if isinstance(res, dict):
                    res["data_freshness"] = "cached_fallback"
                return res, True
            raise
