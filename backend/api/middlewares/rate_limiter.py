"""Token Bucket rate limiter middleware (§13, §19.22).

Named-bucket abstraction designed for extensibility: the `api` bucket is
wired now; the `chat` bucket will be added in Sprint 3 by registering
a new bucket configuration — no refactoring of a hardcoded single-bucket
implementation needed.

Backed by a single atomic Redis Lua script (EVALSHA) so there is no race
between concurrent requests for the same identity.

429 contract (§11, §19.22):
    HTTP 429 with Retry-After header
    Body: { "error": "RATE_LIMITED", "retry_after_seconds": N }
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import redis
from django.conf import settings
from django.http import HttpResponse

from facades.authz import AuthPrincipal

# Atomic Lua script for token bucket consumption.
# Keys: 1) rate_limit_key
# Args: 1) now (unix timestamp as float string), 2) cost, 3) capacity, 4) refill_rate
# Returns: [allowed (0/1), tokens_remaining (int), retry_after_seconds (int)]
_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local cost = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local refill_rate = tonumber(ARGV[4])

local current = redis.call('HMGET', key, 'tokens', 'timestamp')
local tokens = tonumber(current[1])
local timestamp = tonumber(current[2])

if tokens == nil then
    tokens = capacity
    timestamp = now
end

local delta = now - timestamp
local filled = math.min(capacity, tokens + delta * refill_rate)

if filled < cost then
    local retry_after = math.ceil((cost - filled) / refill_rate)
    redis.call('HMSET', key, 'tokens', filled, 'timestamp', now)
    redis.call('EXPIRE', key, 3600)
    return {0, math.floor(filled), retry_after}
end

local remaining = filled - cost
redis.call('HMSET', key, 'tokens', remaining, 'timestamp', now)
redis.call('EXPIRE', key, 3600)
return {1, math.floor(remaining), 0}
"""

_TOKEN_BUCKET_SHA = hashlib.sha1(_TOKEN_BUCKET_LUA.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class BucketConfig:
    name: str
    capacity: int
    refill_rate: float
    ttl: int = 3600


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    tokens_remaining: int
    retry_after_seconds: int


_BUCKET_CONFIGS: dict[str, BucketConfig] = {
    "api": BucketConfig(name="api", capacity=60, refill_rate=1.0),
    "chat": BucketConfig(name="chat", capacity=30, refill_rate=0.5),
}


class RateLimiter:
    """Atomic token-bucket rate limiter backed by Redis Lua script.

    Named-bucket abstraction: each bucket has its own config. The `api`
    bucket is fully wired; the `chat` bucket config is defined but not
    yet applied to any endpoint (Sprint 3).

    Usage:
        limiter = RateLimiter()
        decision = limiter.consume(bucket="api", identity="user:abc", cost=1)
        if not decision.allowed:
            return 429 with Retry-After: decision.retry_after_seconds
    """

    KEY_PREFIX = "rate_limit"

    def __init__(self, *, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client
        self._sha: str | None = None

    def consume(
        self,
        *,
        bucket: str,
        identity: str,
        cost: int = 1,
    ) -> RateLimitDecision:
        """Atomically consume tokens from the bucket for the given identity.

        Returns a RateLimitDecision. If not allowed, retry_after_seconds
        tells the caller how many seconds to wait before retrying.
        """
        config = _BUCKET_CONFIGS.get(bucket)
        if config is None:
            raise ValueError(f"Unknown rate-limit bucket: {bucket}")

        key = f"{self.KEY_PREFIX}:{bucket}:{identity}"
        now = time.time()

        client = self._get_redis()
        if client is None:
            # No Redis available — fail open (don't block requests).
            return RateLimitDecision(
                allowed=True,
                tokens_remaining=config.capacity,
                retry_after_seconds=0,
            )

        try:
            result = client.evalsha(
                self._get_sha(client),
                1,
                key,
                str(now),
                str(cost),
                str(config.capacity),
                str(config.refill_rate),
            )
            allowed = int(result[0]) == 1
            remaining = int(result[1])
            retry_after = int(result[2])
            return RateLimitDecision(
                allowed=allowed,
                tokens_remaining=remaining,
                retry_after_seconds=retry_after,
            )
        except redis.exceptions.NoScriptError:
            result = client.eval(
                _TOKEN_BUCKET_LUA,
                1,
                key,
                str(now),
                str(cost),
                str(config.capacity),
                str(config.refill_rate),
            )
            allowed = int(result[0]) == 1
            remaining = int(result[1])
            retry_after = int(result[2])
            return RateLimitDecision(
                allowed=allowed,
                tokens_remaining=remaining,
                retry_after_seconds=retry_after,
            )

    def _get_redis(self) -> redis.Redis | None:
        if self._redis is not None:
            return self._redis
        if not settings.REDIS_HOST:
            return None
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

    def _get_sha(self, client: redis.Redis) -> str:
        if self._sha is None:
            self._sha = client.script_load(_TOKEN_BUCKET_LUA)
        return self._sha


def _identity_from_request(request) -> str | None:
    """Extract identity string for rate limiting from the request.

    Priority:
    1. Authenticated principal's user_id (from JWT)
    2. API key header
    Falls back to client IP if neither is available.
    """
    principal: AuthPrincipal | None = getattr(request, "_auth_principal", None)
    if principal is not None:
        return f"user:{principal.user_id}"

    api_key = request.META.get("HTTP_X_API_KEY") or request.META.get("API_KEY")
    if api_key:
        return f"api_key:{api_key}"

    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded and forwarded.strip():
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"ip:{ip}"


def _endpoint_cost(request) -> int:
    """Variable per-endpoint cost (§13, §19.22).

    Default: 1 token per request.
    POST /agent/trigger-summary: 5 tokens (reserved for Sprint 2's
    agent trigger endpoint, implemented now per spec requirement).
    """
    path = request.path_info
    method = request.method

    if method == "POST" and _matches_trigger_summary(path):
        return 5
    return 1


def _matches_trigger_summary(path: str) -> bool:
    """Check if the path matches the trigger-summary endpoint pattern."""
    return "/agent/trigger-summary" in path


class RateLimitMiddleware:
    """Edge-layer middleware that enforces token-bucket rate limiting.

    Applied before the Controller/view logic. On 429, returns immediately
    with the exact contract from §11:
        HTTP 429, Retry-After header
        { "error": "RATE_LIMITED", "retry_after_seconds": N }
    """

    def __init__(self, get_response: Callable[[Any], HttpResponse]) -> None:
        self.get_response = get_response
        self._limiter: RateLimiter | None = None

    def __call__(self, request) -> HttpResponse:
        identity = _identity_from_request(request)
        cost = _endpoint_cost(request)

        bucket = "api"
        if "/chat/" in request.path_info:
            bucket = "chat"

        decision = self._get_limiter().consume(
            bucket=bucket,
            identity=identity or "unknown",
            cost=cost,
        )

        if not decision.allowed:
            retry_after = decision.retry_after_seconds
            response = HttpResponse(
                content=json.dumps({
                    "error": "RATE_LIMITED",
                    "retry_after_seconds": retry_after,
                }),
                content_type="application/json",
                status=429,
            )
            response["Retry-After"] = str(retry_after)
            response["X-RateLimit-Remaining"] = str(decision.tokens_remaining)
            return response

        response = self.get_response(request)
        if response is not None:
            response["X-RateLimit-Remaining"] = str(decision.tokens_remaining)
        return response

    def _get_limiter(self) -> RateLimiter:
        if self._limiter is None:
            self._limiter = RateLimiter()
        return self._limiter


__all__ = [
    "BucketConfig",
    "RateLimitDecision",
    "RateLimitMiddleware",
    "RateLimiter",
]
