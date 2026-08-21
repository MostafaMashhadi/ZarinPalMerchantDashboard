"""Refresh-token revocation store for rotation-on-refresh and logout (§19.2, §19.3)."""

from __future__ import annotations

import threading

import redis
from django.conf import settings


class RefreshTokenRepository:
    _KEY_PREFIX = "auth:refresh:revoked:"

    def __init__(self) -> None:
        self._fallback: dict[str, int] = {}
        self._fallback_lock = threading.Lock()
        self._client: redis.Redis | None = None

    def revoke(self, jti: str, *, ttl_seconds: int) -> None:
        key = f"{self._KEY_PREFIX}{jti}"
        client = self._get_client()
        if client is not None:
            client.setex(key, ttl_seconds, "1")
            return
        with self._fallback_lock:
            self._fallback[jti] = ttl_seconds

    def is_revoked(self, jti: str) -> bool:
        key = f"{self._KEY_PREFIX}{jti}"
        client = self._get_client()
        if client is not None:
            return bool(client.exists(key))
        with self._fallback_lock:
            return jti in self._fallback

    def _get_client(self) -> redis.Redis | None:
        if self._client is not None:
            return self._client
        if not settings.REDIS_HOST:
            return None
        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True,
                socket_connect_timeout=1,
            )
            self._client.ping()
        except (redis.RedisError, OSError):
            self._client = None
        return self._client
