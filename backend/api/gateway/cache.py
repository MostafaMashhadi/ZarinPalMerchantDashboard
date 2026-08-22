"""Response cache for LLM gateway (§9.3, §9.6.5).

Cache key construction differs by scope:
- agent: includes ingest_batch_id (ensures a re-run against unchanged data
  is a guaranteed cache hit regardless of which tier last served it).
- chat: fingerprint of (merchant_id, resolved kind, period, decile/category params).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import redis


class LLMResponseCache:
    """Gateway-level response cache (§9.3, §9.6.5).

    Stores DraftResponse results keyed by scope-appropriate fingerprints.
    """

    TTL_SECONDS = 3600

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client or self._connect_redis()

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
    def agent_cache_key(
        merchant_id: str, ingest_batch_id: str | None, system_prompt: str
    ) -> str:
        """Cache key for agentic calls — includes ingest_batch_id (§9.3)."""
        batch_part = ingest_batch_id or "no-batch"
        raw = f"agent:{merchant_id}:{batch_part}:{system_prompt[:100]}"
        return f"llm_cache:{hashlib.md5(raw.encode()).hexdigest()}"

    @staticmethod
    def chat_cache_key(
        merchant_id: str,
        resolved_kind: str,
        period_start: str,
        period_end: str,
        **params: Any,
    ) -> str:
        """Cache key for chat calls — fingerprint of query params (§9.6.5).

        Includes (merchant_id, resolved kind, period, decile/category params).
        """
        fingerprint_data = {
            "merchant_id": merchant_id,
            "kind": resolved_kind,
            "period_start": period_start,
            "period_end": period_end,
            "params": params,
        }
        raw = json.dumps(fingerprint_data, sort_keys=True, default=str)
        return f"llm_cache:chat:{hashlib.md5(raw.encode()).hexdigest()}"

    def get(self, key: str) -> str | None:
        if not self._redis:
            return None
        try:
            return self._redis.get(key)
        except redis.RedisError:
            return None

    def set(self, key: str, value: str) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(key, self.TTL_SECONDS, value)
        except redis.RedisError:
            pass

    def hit(self, key: str) -> bool:
        if not self._redis:
            return False
        try:
            return bool(self._redis.exists(key))
        except redis.RedisError:
            return False


__all__ = ["LLMResponseCache"]
