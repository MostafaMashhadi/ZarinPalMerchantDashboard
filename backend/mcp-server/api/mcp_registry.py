"""MCP auth registry — maps API keys and mTLS certs to merchant principals (§9.4).

In production, this would query a database. For testability, it's a
module-level dict that can be populated at startup or test time.
"""

from __future__ import annotations

from typing import Any

API_KEY_REGISTRY: dict[str, dict[str, Any]] = {}

CERT_REGISTRY: dict[str, dict[str, Any]] = {}

API_KEY_SECRET = "test-api-key-secret"


def register_api_key(key_id: str, config: dict[str, Any]) -> None:
    API_KEY_REGISTRY[key_id] = config


def register_cert(dn: str, config: dict[str, Any]) -> None:
    CERT_REGISTRY[dn] = config


__all__ = [
    "API_KEY_REGISTRY",
    "API_KEY_SECRET",
    "CERT_REGISTRY",
    "register_api_key",
    "register_cert",
]
