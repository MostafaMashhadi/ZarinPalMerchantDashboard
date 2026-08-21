"""Merchant bounded-context facade — shared entry point for REST and MCP (§2)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from facades.authz import AuthPrincipal, AuthzStub
from services.auth_exceptions import (
    AccountLockedError,
    AuthError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from services.auth_service import AuthService, LoginResult


@dataclass(frozen=True, slots=True)
class LoginResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


@dataclass(frozen=True, slots=True)
class RefreshResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class MerchantFacade:
    def __init__(
        self,
        *,
        auth_service: AuthService | None = None,
        authz: AuthzStub | None = None,
    ) -> None:
        self._auth = auth_service or AuthService()
        self._authz = authz or AuthzStub()

    def login(self, *, email: str, password: str, ip_address: str | None = None) -> LoginResponse:
        result = self._auth.login(email=email, password=password, ip_address=ip_address)
        return self._to_login_response(result)

    def refresh(self, *, refresh_token: str) -> RefreshResponse:
        tokens = self._auth.refresh(refresh_token=refresh_token)
        return RefreshResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.access_expires_in,
        )

    def logout(self, *, refresh_token: str) -> None:
        self._auth.logout(refresh_token=refresh_token)

    def require_merchant_access(
        self,
        principal: AuthPrincipal | None,
        merchant_id: uuid.UUID,
    ) -> None:
        """Object-level AuthZ stub — delegates to AuthzStub (Task 2.4 completes enforcement)."""
        self._authz.require_merchant_access(principal, merchant_id)

    @staticmethod
    def _to_login_response(result: LoginResult) -> LoginResponse:
        return LoginResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_in=result.expires_in,
        )


__all__ = [
    "AccountLockedError",
    "AuthError",
    "AuthPrincipal",
    "InvalidCredentialsError",
    "InvalidRefreshTokenError",
    "LoginResponse",
    "MerchantFacade",
    "RefreshResponse",
]
