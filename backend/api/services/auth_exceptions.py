"""Auth-related domain exceptions."""

from dataclasses import dataclass
from datetime import datetime


class AuthError(Exception):
    """Base auth failure."""


class InvalidCredentialsError(AuthError):
    """Generic login failure — same message whether email exists or password wrong (§19.1)."""


@dataclass(frozen=True, slots=True)
class AccountLockedError(AuthError):
    locked_until: datetime


class InvalidRefreshTokenError(AuthError):
    """Refresh token invalid, expired, or revoked (§19.2)."""
