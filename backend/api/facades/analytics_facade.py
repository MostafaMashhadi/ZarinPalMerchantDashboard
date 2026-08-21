"""Dashboard summary facade — cache-aside Redis with ClickHouse fallback (§5.4, §7.3, §19.4).

Provides:
  - get_dashboard_summary: cached per-merchant summary via Redis, falling
    back to ClickHouse rollups on cache miss.
  - run_analysis: dispatches to the correct AnalysisStrategy via
    AnalysisStrategyFactory (§6.2).

Spec §19.4 references dashboard summary with cache-aside Redis. The
full circuit-breaker is Task 2.5, but this facade implements the
basic cache-aside pattern.

All methods enforce object-level AuthZ (§13, §19.23) before doing
any data access. Controllers pass the authenticated principal.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any
from uuid import UUID

import redis
from django.conf import settings
from django.utils import timezone

from analytics.strategy_factory import AnalysisStrategyFactory
from facades.authz import AuthPrincipal, AuthzEnforcer
from repositories.transaction_repository import TransactionRepository
from shared.dtos import AnalysisParams, AnalysisResult


class AnalyticsFacade:
    """Shared entry point for dashboard summary and analysis endpoints.

    Controllers call facade methods; the facade coordinates caching,
    strategy dispatch, and repository access.
    """

    _SUMMARY_CACHE_TTL = 300
    _SUMMARY_CACHE_PREFIX = "dashboard:summary:"

    def __init__(
        self,
        *,
        repo: TransactionRepository | None = None,
        strategy_factory: AnalysisStrategyFactory | None = None,
        authz: AuthzEnforcer | None = None,
    ) -> None:
        self._repo = repo or TransactionRepository()
        self._factory = strategy_factory or AnalysisStrategyFactory()
        self._authz = authz or AuthzEnforcer()
        self._redis: redis.Redis | None = None
        self._redis_lock = threading.Lock()

    def get_dashboard_summary(
        self,
        merchant_id: UUID,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        *,
        principal: AuthPrincipal | None = None,
    ) -> dict[str, Any]:
        """Return cached dashboard summary or compute from ClickHouse.

        Cache-aside pattern (§19.4): try Redis first, on miss query
        ClickHouse rollups and populate cache.

        AuthZ (§13): principal must be entitled to merchant_id before
        any data access.
        """
        self._authz.check_object_permission(principal, merchant_id)
        now = timezone.now()
        if period_start is None:
            from datetime import timedelta

            period_start = now - timedelta(days=30)
        if period_end is None:
            period_end = now

        cache_key = (
            f"{self._SUMMARY_CACHE_PREFIX}{merchant_id}:"
            f"{period_start.isoformat()}:{period_end.isoformat()}"
        )

        cached = self._try_get_cached(cache_key)
        if cached is not None:
            result = json.loads(cached)
            result["data_freshness"] = "cached"
            return result

        summary = self._repo.get_merchant_summary(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )

        result: dict[str, Any] = {
            "merchant_id": str(merchant_id),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "data_freshness": "fresh",
            "summary": summary,
        }

        self._try_set_cached(cache_key, result, ttl=self._SUMMARY_CACHE_TTL)
        return result

    def run_analysis(
        self,
        merchant_id: UUID,
        kind: str,
        params: AnalysisParams,
        *,
        principal: AuthPrincipal | None = None,
    ) -> AnalysisResult:
        """Dispatch to the correct AnalysisStrategy via the factory (§6.2).

        AuthZ (§13): principal must be entitled to merchant_id.
        """
        self._authz.check_object_permission(principal, merchant_id)
        strategy = self._factory.create(kind)
        result = strategy.compute(merchant_id, params)

        self._invalidate_dashboard_cache(merchant_id)

        return result

    def _get_redis(self) -> redis.Redis | None:
        if self._redis is not None:
            return self._redis
        if not settings.REDIS_HOST:
            return None
        with self._redis_lock:
            if self._redis is not None:
                return self._redis
            try:
                client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
                client.ping()
                self._redis = client
            except (redis.RedisError, OSError):
                self._redis = None
            return self._redis

    def _try_get_cached(self, key: str) -> str | None:
        client = self._get_redis()
        if client is None:
            return None
        try:
            return client.get(key)
        except redis.RedisError:
            return None

    def _try_set_cached(self, key: str, value: dict[str, Any], *, ttl: int) -> None:
        client = self._get_redis()
        if client is None:
            return
        try:
            client.setex(key, ttl, json.dumps(value))
        except redis.RedisError:
            pass

    def _invalidate_dashboard_cache(self, merchant_id: UUID) -> None:
        """Invalidate cached dashboard summary after an analysis run."""
        client = self._get_redis()
        if client is None:
            return
        try:
            for key in client.scan_iter(f"{self._SUMMARY_CACHE_PREFIX}{merchant_id}:*"):
                client.delete(key)
        except redis.RedisError:
            pass


__all__ = ["AnalyticsFacade"]
