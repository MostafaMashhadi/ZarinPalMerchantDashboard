"""Object-level authorization stub — real enforcement lands in Task 2.4."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user_id: uuid.UUID
    merchant_id: uuid.UUID
    role: str
    email: str


class AuthzStub:
    """Placeholder AuthZ gate invoked by every Facade method that touches merchant data."""

    def require_merchant_access(
        self,
        principal: AuthPrincipal | None,
        merchant_id: uuid.UUID,
    ) -> None:
        """Stub: no enforcement yet (Task 2.4). Signature kept for uniform Facade calls."""
        _ = (principal, merchant_id)
