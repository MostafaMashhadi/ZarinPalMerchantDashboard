"""Portal authentication — login (§19.1), refresh (§19.2), logout (§19.3)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password

from merchants.models import AuditLog
from repositories.merchant_user_repository import MerchantUserRepository
from repositories.refresh_token_repository import RefreshTokenRepository
from services.auth_exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from services.jwt_service import JwtService, TokenPair

LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class LoginResult:
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: uuid.UUID
    merchant_id: uuid.UUID
    role: str
    email: str


class AuthService:
    def __init__(
        self,
        *,
        user_repository: MerchantUserRepository | None = None,
        refresh_token_repository: RefreshTokenRepository | None = None,
        jwt_service: JwtService | None = None,
    ) -> None:
        self._users = user_repository or MerchantUserRepository()
        self._refresh_tokens = refresh_token_repository or RefreshTokenRepository()
        self._jwt = jwt_service or JwtService()

    def login(self, *, email: str, password: str, ip_address: str | None) -> LoginResult:
        user = self._users.get_by_email(email)
        password_hash = user.password_hash if user else self._users.dummy_password_hash()

        if user and self._users.is_locked(user.locked_until):
            raise AccountLockedError(locked_until=user.locked_until)  # type: ignore[arg-type]

        password_ok = check_password(password, password_hash)
        if user is None or not password_ok:
            if user is not None:
                locked_until = None
                next_attempts = user.failed_login_attempts + 1
                if next_attempts >= LOCKOUT_MAX_ATTEMPTS:
                    locked_until = self._lockout_deadline()
                self._users.record_failed_login(user.id, locked_until=locked_until)
            raise InvalidCredentialsError

        from django.utils import timezone

        now = timezone.now()
        self._users.record_successful_login(user.id, login_at=now)
        tokens = self._jwt.issue_token_pair(
            user_id=user.id,
            merchant_id=user.merchant_id,
            role=user.role,
            email=user.email,
        )
        AuditLog.objects.create(
            merchant_user_id=user.id,
            action="auth.login",
            metadata={"email": user.email},
            ip_address=ip_address,
        )
        return LoginResult(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.access_expires_in,
            user_id=user.id,
            merchant_id=user.merchant_id,
            role=user.role,
            email=user.email,
        )

    def refresh(self, *, refresh_token: str) -> TokenPair:
        try:
            claims = self._jwt.decode_refresh_token(refresh_token)
        except jwt.InvalidTokenError as exc:
            raise InvalidRefreshTokenError from exc

        if self._refresh_tokens.is_revoked(claims.jti):
            raise InvalidRefreshTokenError

        user = self._users.get_by_id(claims.user_id)
        if user is None:
            raise InvalidRefreshTokenError

        if self._users.is_locked(user.locked_until):
            raise InvalidRefreshTokenError

        self._refresh_tokens.revoke(
            claims.jti,
            ttl_seconds=settings.JWT_REFRESH_TTL_SECONDS,
        )
        return self._jwt.issue_token_pair(
            user_id=user.id,
            merchant_id=user.merchant_id,
            role=user.role,
            email=user.email,
        )

    def logout(self, *, refresh_token: str) -> None:
        try:
            claims = self._jwt.decode_refresh_token(refresh_token)
        except jwt.InvalidTokenError:
            return

        self._refresh_tokens.revoke(
            claims.jti,
            ttl_seconds=settings.JWT_REFRESH_TTL_SECONDS,
        )

    @staticmethod
    def _lockout_deadline():
        from django.utils import timezone

        return timezone.now() + LOCKOUT_DURATION
