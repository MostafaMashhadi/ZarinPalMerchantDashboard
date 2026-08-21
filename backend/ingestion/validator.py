from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

VALID_SESSION_STATUSES = frozenset({"Verified", "Paid", "InBank", "Failed", "Reversed"})
VALID_TRY_STATUSES = frozenset({"NoAttempt", "Failed", "InBank", "Verified", "Paid", "Reversed"})
VALID_VERIFY_TYPES = frozenset({"Automated", "Manual"})
PSP_CODE_PATTERN = re.compile(r"^PSP-\d+:.+$")


class ValidationError(Exception):
    """Base exception for ingestion row validation errors."""

    def __init__(self, message: str, row_index: int | None = None, column: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.row_index = row_index
        self.column = column

    def __str__(self) -> str:
        loc = f" (row {self.row_index}" if self.row_index is not None else ""
        if self.column and loc:
            loc += f", col '{self.column}')"
        elif loc:
            loc += ")"
        return f"{self.message}{loc}"


def parse_datetime(val: Any) -> str | None:
    """Parse string or timestamp into ClickHouse DateTime formatted string ('YYYY-MM-DD HH:MM:SS')."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "nan", ""):
        return None
    # Handle ISO or standard formats
    s = s.replace("T", " ")
    if s.endswith("Z"):
        s = s[:-1]
    # Remove microseconds/timezone offset if present for ClickHouse DateTime
    if "+" in s:
        s = s.split("+")[0].strip()
    if "." in s:
        parts = s.split(".")
        s = parts[0]
    return s


def parse_nullable_int(val: Any) -> int | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "nan", ""):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def parse_nullable_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "nan", ""):
        return None
    return s


@dataclass(frozen=True)
class ValidatedRow:
    """Normalized, type-safe representation of a single transaction row for ClickHouse."""

    session_key: int
    try_seq: int
    terminal_key: str
    merchant_key: str
    category_id: str
    category_title: str
    amount: int
    adjusted_fee: int
    session_status: str
    try_status: str
    switch_response_code: str
    psp_code: str
    issuer_bank_code: str
    payer_card_key: str
    verify_type: str
    init_time_ms: int | None
    verify_time_ms: int | None
    created_at: str
    try_created_at: str | None
    verified_at: str | None
    settled_at: str | None
    expire_in: str
    ingest_batch_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_key": self.session_key,
            "try_seq": self.try_seq,
            "terminal_key": self.terminal_key,
            "merchant_key": self.merchant_key,
            "category_id": self.category_id,
            "category_title": self.category_title,
            "amount": self.amount,
            "adjusted_fee": self.adjusted_fee,
            "session_status": self.session_status,
            "try_status": self.try_status,
            "switch_response_code": self.switch_response_code,
            "psp_code": self.psp_code,
            "issuer_bank_code": self.issuer_bank_code,
            "payer_card_key": self.payer_card_key,
            "verify_type": self.verify_type,
            "init_time_ms": self.init_time_ms,
            "verify_time_ms": self.verify_time_ms,
            "created_at": self.created_at,
            "try_created_at": self.try_created_at,
            "verified_at": self.verified_at,
            "settled_at": self.settled_at,
            "expire_in": self.expire_in,
            "ingest_batch_id": self.ingest_batch_id,
        }


class RowValidator:
    """Validates raw CSV row dictionaries against the schema and domain rules (§2.2, §5.4)."""

    def validate_row(
        self,
        raw: dict[str, Any],
        batch_id: UUID,
        row_index: int | None = None,
    ) -> ValidatedRow:
        # 1. Mandatory integer keys
        try:
            session_key = int(raw.get("session_key", 0))
        except (ValueError, TypeError) as e:
            raise ValidationError("Invalid session_key integer", row_index, "session_key") from e

        try:
            try_seq = int(raw.get("try_seq", 0))
        except (ValueError, TypeError) as e:
            raise ValidationError("Invalid try_seq integer", row_index, "try_seq") from e

        try:
            amount = int(float(raw.get("amount", 0)))
        except (ValueError, TypeError) as e:
            raise ValidationError("Invalid amount integer", row_index, "amount") from e

        try:
            adjusted_fee = int(float(raw.get("adjusted_fee", 0)))
        except (ValueError, TypeError) as e:
            raise ValidationError("Invalid adjusted_fee integer", row_index, "adjusted_fee") from e

        # 2. String keys
        terminal_key = str(raw.get("terminal_key", "")).strip()
        merchant_key = str(raw.get("merchant_key", "")).strip()
        category_id = str(raw.get("category_id", "")).strip()
        category_title = str(raw.get("category_title", "")).strip()

        if not merchant_key:
            raise ValidationError("merchant_key must not be empty", row_index, "merchant_key")
        if not terminal_key:
            raise ValidationError("terminal_key must not be empty", row_index, "terminal_key")

        # 3. Status enums
        session_status = str(raw.get("session_status", "")).strip()
        if session_status not in VALID_SESSION_STATUSES:
            raise ValidationError(
                f"Invalid session_status '{session_status}'. Expected one of {sorted(VALID_SESSION_STATUSES)}",
                row_index,
                "session_status",
            )

        try_status = str(raw.get("try_status", "")).strip()
        if try_status not in VALID_TRY_STATUSES:
            raise ValidationError(
                f"Invalid try_status '{try_status}'. Expected one of {sorted(VALID_TRY_STATUSES)}",
                row_index,
                "try_status",
            )

        verify_type = str(raw.get("verify_type", "")).strip()
        if verify_type not in VALID_VERIFY_TYPES:
            raise ValidationError(
                f"Invalid verify_type '{verify_type}'. Expected one of {sorted(VALID_VERIFY_TYPES)}",
                row_index,
                "verify_type",
            )

        # 4. Mandatory DateTime columns
        # Column name in CSV might be expire_in or expire_at (normalized to expire_in)
        expire_in_raw = raw.get("expire_in") or raw.get("expire_at")
        expire_in = parse_datetime(expire_in_raw)
        if not expire_in:
            raise ValidationError("expire_in is mandatory and cannot be null", row_index, "expire_in")

        created_at_raw = raw.get("created_at")
        created_at = parse_datetime(created_at_raw)
        if not created_at:
            raise ValidationError("created_at is mandatory and cannot be null", row_index, "created_at")

        # 5. Status-conditional columns & nullability (§2.2)
        # switch_response_code: non-null must match PSP-\d+:.+
        switch_code = parse_nullable_str(raw.get("switch_response_code"))
        if switch_code is not None:
            if not PSP_CODE_PATTERN.match(switch_code):
                raise ValidationError(
                    f"switch_response_code '{switch_code}' does not match PSP-namespaced format 'PSP-xx:code'",
                    row_index,
                    "switch_response_code",
                )
        switch_response_code_str = switch_code if switch_code is not None else ""

        # try_created_at: null when try_seq = 0 / NoAttempt
        try_created_at = parse_datetime(raw.get("try_created_at"))
        if try_seq == 0 or try_status == "NoAttempt":
            # Allowed to be null
            pass
        elif try_created_at is None:
            # If try_seq > 0, an attempt was made and should have a try_created_at
            # but if dataset omitted it, fallback to created_at
            try_created_at = created_at

        # psp_code, issuer_bank_code, payer_card_key
        psp_code = parse_nullable_str(raw.get("psp_code")) or ""
        issuer_bank_code = parse_nullable_str(raw.get("issuer_bank_code")) or ""
        payer_card_key = parse_nullable_str(raw.get("payer_card_key")) or ""

        # Timing columns
        init_time_ms = parse_nullable_int(raw.get("init_time_ms"))
        verify_time_ms = parse_nullable_int(raw.get("verify_time_ms"))

        # Datetime columns
        verified_at = parse_datetime(raw.get("verified_at"))
        settled_at = parse_datetime(raw.get("settled_at"))

        return ValidatedRow(
            session_key=session_key,
            try_seq=try_seq,
            terminal_key=terminal_key,
            merchant_key=merchant_key,
            category_id=category_id,
            category_title=category_title,
            amount=amount,
            adjusted_fee=adjusted_fee,
            session_status=session_status,
            try_status=try_status,
            switch_response_code=switch_response_code_str,
            psp_code=psp_code,
            issuer_bank_code=issuer_bank_code,
            payer_card_key=payer_card_key,
            verify_type=verify_type,
            init_time_ms=init_time_ms,
            verify_time_ms=verify_time_ms,
            created_at=created_at,
            try_created_at=try_created_at,
            verified_at=verified_at,
            settled_at=settled_at,
            expire_in=expire_in,
            ingest_batch_id=str(batch_id),
        )
