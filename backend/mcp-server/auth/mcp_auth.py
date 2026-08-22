"""MCP server auth — mTLS or signed API keys (§9.4, §13).

NOT JWT. MCP clients authenticate via:
1. Signed API key (preferred for programmatic clients)
2. mTLS certificate (for service-to-service)

Both methods resolve to a principal: (merchant_id, user_id, role, email).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class McpPrincipal:
    """MCP authentication principal — equivalent to AuthPrincipal (§9.4)."""

    merchant_id: UUID
    user_id: UUID
    role: str
    email: str


class McpAuthService:
    """Authenticates MCP requests via signed API key or mTLS (§9.4, §13).

    Signed API key format: {key_id}.{timestamp}.{signature}
    - key_id: identifies the API key
    - timestamp: Unix timestamp (prevents replay within TTL)
    - signature: HMAC-SHA256 of "key_id:timestamp" using the secret

    mTLS: distinguished_name maps to merchant_id via certificate registry.
    """

    def __init__(self, *, api_key_secret: str | None = None) -> None:
        self._api_key_secret = api_key_secret

    def authenticate(
        self,
        *,
        api_key: str | None = None,
        client_cert: dict[str, str] | None = None,
    ) -> McpPrincipal | None:
        """Authenticate and return principal (§9.4).

        Tries API key first, then mTLS. Returns None if neither validates.
        """
        if api_key:
            return self._authenticate_api_key(api_key)
        if client_cert:
            return self._authenticate_mtls(client_cert)
        return None

    def _authenticate_api_key(self, api_key: str) -> McpPrincipal | None:
        """Validate a signed API key (§9.4).

        Format: key_id.timestamp.signature
        """
        parts = api_key.split(".")
        if len(parts) != 3:
            return None

        key_id, timestamp_str, signature = parts

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return None

        now = int(time.time())
        if now - timestamp > 300:  # 5-minute TTL
            return None
        if timestamp - now > 300:  # allow 5 minutes clock skew
            return None

        expected_sig = hmac.new(
            self._api_key_secret.encode() if self._api_key_secret else b"",
            f"{key_id}:{timestamp}".encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        return self._lookup_api_key_owner(key_id)

    def _authenticate_mtls(
        self, client_cert: dict[str, str]
    ) -> McpPrincipal | None:
        """Validate mTLS client certificate (§9.4).

        Uses the distinguished_name to look up the merchant mapping.
        """
        dn = client_cert.get("subject", "")
        return self._lookup_cert_owner(dn)

    def _lookup_api_key_owner(self, key_id: str) -> McpPrincipal | None:
        """Look up which merchant a signed API key belongs to (§9.4).

        In production, this queries a database or key registry.
        """
        from api.mcp_registry import API_KEY_REGISTRY

        config = API_KEY_REGISTRY.get(key_id)
        if config is None:
            return None

        return McpPrincipal(
            merchant_id=UUID(config["merchant_id"]),
            user_id=UUID(config["user_id"]),
            role=config.get("role", "admin"),
            email=config.get("email", ""),
        )

    def _lookup_cert_owner(self, dn: str) -> McpPrincipal | None:
        """Look up which merchant an mTLS certificate belongs to (§9.4)."""
        from api.mcp_registry import CERT_REGISTRY

        config = CERT_REGISTRY.get(dn)
        if config is None:
            return None

        return McpPrincipal(
            merchant_id=UUID(config["merchant_id"]),
            user_id=UUID(config["user_id"]),
            role=config.get("role", "admin"),
            email=config.get("email", ""),
        )


__all__ = ["McpAuthService", "McpPrincipal"]
