"""JWT issuance and validation for portal auth (§13)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from django.conf import settings

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    merchant_id: uuid.UUID
    role: str
    email: str


@dataclass(frozen=True, slots=True)
class RefreshTokenClaims:
    user_id: uuid.UUID
    jti: str


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int


class JwtService:
    def issue_token_pair(
        self,
        *,
        user_id: uuid.UUID,
        merchant_id: uuid.UUID,
        role: str,
        email: str,
    ) -> TokenPair:
        now = datetime.now(tz=UTC)
        access_expires_in = settings.JWT_ACCESS_TTL_SECONDS
        refresh_expires_in = settings.JWT_REFRESH_TTL_SECONDS
        jti = str(uuid.uuid4())

        access_payload = {
            "sub": str(user_id),
            "merchant_id": str(merchant_id),
            "role": role,
            "email": email,
            "type": TOKEN_TYPE_ACCESS,
            "iat": now,
            "exp": now + timedelta(seconds=access_expires_in),
        }
        refresh_payload = {
            "sub": str(user_id),
            "jti": jti,
            "type": TOKEN_TYPE_REFRESH,
            "iat": now,
            "exp": now + timedelta(seconds=refresh_expires_in),
        }

        access_token = jwt.encode(
            access_payload,
            settings.JWT_ACCESS_SECRET,
            algorithm="HS256",
        )
        refresh_token = jwt.encode(
            refresh_payload,
            settings.JWT_REFRESH_SECRET,
            algorithm="HS256",
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=access_expires_in,
        )

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        payload = self._decode(token, settings.JWT_ACCESS_SECRET)
        if payload.get("type") != TOKEN_TYPE_ACCESS:
            msg = "Invalid access token type"
            raise jwt.InvalidTokenError(msg)
        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            merchant_id=uuid.UUID(payload["merchant_id"]),
            role=payload["role"],
            email=payload["email"],
        )

    def decode_refresh_token(self, token: str) -> RefreshTokenClaims:
        payload = self._decode(token, settings.JWT_REFRESH_SECRET)
        if payload.get("type") != TOKEN_TYPE_REFRESH:
            msg = "Invalid refresh token type"
            raise jwt.InvalidTokenError(msg)
        jti = payload.get("jti")
        if not jti:
            msg = "Refresh token missing jti"
            raise jwt.InvalidTokenError(msg)
        return RefreshTokenClaims(user_id=uuid.UUID(payload["sub"]), jti=jti)

    def _decode(self, token: str, secret: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
