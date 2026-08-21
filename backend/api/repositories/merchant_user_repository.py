"""Persistence gateway for MERCHANT_USER rows — the only layer touching that table."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from merchants.models import MerchantUser


@dataclass(frozen=True, slots=True)
class MerchantUserRecord:
    id: uuid.UUID
    merchant_id: uuid.UUID
    email: str
    password_hash: str
    role: str
    failed_login_attempts: int
    locked_until: datetime | None
    last_login_at: datetime | None


class MerchantUserRepository:
    _DUMMY_PASSWORD_HASH = (
        "pbkdf2_sha256$870000$stub$stubhash=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    )

    def get_by_email(self, email: str) -> MerchantUserRecord | None:
        try:
            user = MerchantUser.objects.select_related("merchant").get(email__iexact=email)
        except MerchantUser.DoesNotExist:
            return None
        return self._to_record(user)

    def get_by_id(self, user_id: uuid.UUID) -> MerchantUserRecord | None:
        try:
            user = MerchantUser.objects.select_related("merchant").get(pk=user_id)
        except MerchantUser.DoesNotExist:
            return None
        return self._to_record(user)

    def dummy_password_hash(self) -> str:
        """Used for constant-time login when email is unknown (§19.1)."""
        return self._DUMMY_PASSWORD_HASH

    def record_failed_login(self, user_id: uuid.UUID, *, locked_until: datetime | None) -> None:
        user = MerchantUser.objects.get(pk=user_id)
        user.failed_login_attempts += 1
        if locked_until is not None:
            user.locked_until = locked_until
        user.save(update_fields=["failed_login_attempts", "locked_until"])

    def record_successful_login(self, user_id: uuid.UUID, *, login_at: datetime) -> None:
        MerchantUser.objects.filter(pk=user_id).update(
            failed_login_attempts=0,
            locked_until=None,
            last_login_at=login_at,
        )

    @staticmethod
    def _to_record(user: MerchantUser) -> MerchantUserRecord:
        return MerchantUserRecord(
            id=user.id,
            merchant_id=user.merchant_id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            last_login_at=user.last_login_at,
        )

    @staticmethod
    def is_locked(locked_until: datetime | None, *, now: datetime | None = None) -> bool:
        if locked_until is None:
            return False
        reference = now or timezone.now()
        return locked_until > reference
