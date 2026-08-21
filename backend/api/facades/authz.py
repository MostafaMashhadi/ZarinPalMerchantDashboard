"""Object-level authorization enforcement (§13, §19.23).

Real AuthZ gate that checks whether the authenticated principal is
entitled to access a given merchant. Reusable by REST, MCP (Sprint 4),
and ChatFacade (Sprint 3) without duplication.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from rest_framework.exceptions import PermissionDenied


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user_id: uuid.UUID
    merchant_id: uuid.UUID
    role: str
    email: str


class AuthzEnforcer:
    """Enforces object-level authorization on every Facade method.

    Replaces AuthzStub — real enforcement per §13 and §19.23.
    Every Facade method that takes a merchant_id calls:
        enforcer.check_object_permission(principal, merchant_id)
    which raises PermissionDenied (403) if the principal is not entitled
    to that merchant.

    404-vs-403 distinction (§19.23):
        - Controller resolves merchant_ref → UUID. If unresolvable → 404.
        - If resolvable but AuthZ fails → 403 (PermissionDenied raised here).
    """

    def check_object_permission(
        self,
        principal: AuthPrincipal | None,
        merchant_id: uuid.UUID,
    ) -> None:
        """Verify principal is entitled to merchant_id. Raises PermissionDenied if not.

        Rules:
        - Anonymous principal (no JWT) → 403.
        - Principal's merchant_id must match the target merchant_id.
          (Single-tenant model: a user belongs to exactly one merchant.)
        - 'owner' and 'admin' roles are implicitly authorized (they own the
          merchant). Other roles are denied unless they match.
        """
        if principal is None:
            raise PermissionDenied(
                detail={"error": "AUTHENTICATION_REQUIRED"},
                code="authentication_required",
            )

        if principal.merchant_id != merchant_id:
            raise PermissionDenied(
                detail={"error": "NOT_ENTITLED_TO_MERCHANT"},
                code="merchant_mismatch",
            )


__all__ = ["AuthPrincipal", "AuthzEnforcer"]
