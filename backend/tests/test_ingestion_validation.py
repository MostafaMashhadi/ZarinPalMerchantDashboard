import uuid

import pytest

from ingestion.validator import RowValidator, ValidationError


@pytest.fixture
def validator() -> RowValidator:
    return RowValidator()


@pytest.fixture
def base_valid_row() -> dict[str, str | int]:
    return {
        "session_key": "123456789",
        "try_seq": "1",
        "terminal_key": "T1001",
        "merchant_key": "M215",
        "category_id": "CAT_RETAIL",
        "category_title": "Retail",
        "amount": "5000000",
        "adjusted_fee": "50000",
        "session_status": "Verified",
        "try_status": "Verified",
        "switch_response_code": "PSP-05:00",
        "psp_code": "PSP-05",
        "issuer_bank_code": "BANK_MELLAT",
        "payer_card_key": "CARD_HASH_123",
        "verify_type": "Automated",
        "init_time_ms": "120",
        "verify_time_ms": "85",
        "created_at": "2026-08-20 10:00:00",
        "try_created_at": "2026-08-20 10:00:05",
        "verified_at": "2026-08-20 10:00:10",
        "settled_at": "2026-08-20 10:00:15",
        "expire_in": "2026-08-20 10:30:00",
    }


def test_validate_row_valid(validator: RowValidator, base_valid_row: dict) -> None:
    batch_id = uuid.uuid4()
    validated = validator.validate_row(base_valid_row, batch_id)

    assert validated.session_key == 123456789
    assert validated.try_seq == 1
    assert validated.amount == 5000000
    assert validated.adjusted_fee == 50000
    assert validated.merchant_key == "M215"
    assert validated.session_status == "Verified"
    assert validated.verify_type == "Automated"
    assert validated.switch_response_code == "PSP-05:00"
    assert validated.ingest_batch_id == str(batch_id)


def test_psp_response_code_shape_validation(validator: RowValidator, base_valid_row: dict) -> None:
    """§2.2: switch_response_code must match PSP-\\d+:.+ format if present."""
    batch_id = uuid.uuid4()

    # Valid shapes
    base_valid_row["switch_response_code"] = "PSP-01:100"
    assert validator.validate_row(base_valid_row, batch_id).switch_response_code == "PSP-01:100"

    base_valid_row["switch_response_code"] = "PSP-25:APPROVED"
    assert validator.validate_row(base_valid_row, batch_id).switch_response_code == "PSP-25:APPROVED"

    # Empty or null is valid (e.g. no attempt or didn't reach switch)
    base_valid_row["switch_response_code"] = ""
    assert validator.validate_row(base_valid_row, batch_id).switch_response_code == ""

    # Invalid shapes must be rejected
    base_valid_row["switch_response_code"] = "56"
    with pytest.raises(ValidationError) as exc:
        validator.validate_row(base_valid_row, batch_id)
    assert "switch_response_code" in str(exc.value)

    base_valid_row["switch_response_code"] = "CODE_56"
    with pytest.raises(ValidationError) as exc:
        validator.validate_row(base_valid_row, batch_id)
    assert "switch_response_code" in str(exc.value)


def test_status_enums_validation(validator: RowValidator, base_valid_row: dict) -> None:
    batch_id = uuid.uuid4()

    # Reversed is valid session_status
    base_valid_row["session_status"] = "Reversed"
    assert validator.validate_row(base_valid_row, batch_id).session_status == "Reversed"

    # Invalid session_status
    base_valid_row["session_status"] = "UnknownStatus"
    with pytest.raises(ValidationError) as exc:
        validator.validate_row(base_valid_row, batch_id)
    assert "session_status" in str(exc.value)

    # Invalid verify_type
    base_valid_row["session_status"] = "Verified"
    base_valid_row["verify_type"] = "SemiAutomated"
    with pytest.raises(ValidationError) as exc:
        validator.validate_row(base_valid_row, batch_id)
    assert "verify_type" in str(exc.value)


def test_mandatory_expire_in_and_created_at(validator: RowValidator, base_valid_row: dict) -> None:
    """§2.2: expire_in is always present (never null/empty)."""
    batch_id = uuid.uuid4()

    # Missing expire_in
    base_valid_row["expire_in"] = ""
    with pytest.raises(ValidationError) as exc:
        validator.validate_row(base_valid_row, batch_id)
    assert "expire_in" in str(exc.value)

    # Fallback to expire_at if CSV header used old name
    del base_valid_row["expire_in"]
    base_valid_row["expire_at"] = "2026-08-20 10:30:00"
    validated = validator.validate_row(base_valid_row, batch_id)
    assert validated.expire_in == "2026-08-20 10:30:00"


def test_noattempt_nullable_try_created_at(validator: RowValidator, base_valid_row: dict) -> None:
    """§2.2: try_seq = 0 / NoAttempt rows have nullable try_created_at."""
    batch_id = uuid.uuid4()
    base_valid_row["try_seq"] = "0"
    base_valid_row["try_status"] = "NoAttempt"
    base_valid_row["try_created_at"] = ""

    validated = validator.validate_row(base_valid_row, batch_id)
    assert validated.try_seq == 0
    assert validated.try_status == "NoAttempt"
    assert validated.try_created_at is None
