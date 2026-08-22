"""Shared merchant_ref resolution — identical logic for REST and MCP (§5.2, §19.23).

Both REST controllers and MCP tools resolve merchant_ref (UUID or key)
to an internal UUID exactly the same way.

This module lives in the shared package (backend/shared/shared/) so that
both the API layer and the MCP server can import it.
"""

from __future__ import annotations

from uuid import UUID


def resolve_merchant_ref(merchant_ref: str) -> UUID | None:
    """Resolve merchant_ref (UUID string or merchant_key) to internal UUID.

    404-vs-403 distinction (§19.23):
    - Unresolvable merchant_ref → None (caller returns 404)
    - Resolvable but AuthZ fails → caller returns 403
    """
    try:
        return UUID(merchant_ref)
    except (ValueError, AttributeError):
        pass

    from merchants.models import Merchant

    try:
        merchant = Merchant.objects.get(merchant_key__iexact=merchant_ref)
        return merchant.id
    except Merchant.DoesNotExist:
        return None


__all__ = ["resolve_merchant_ref"]
