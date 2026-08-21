import uuid
from unittest.mock import MagicMock

import pytest

from ingestion.pipeline import CSVIngestionPipeline, IngestionPipelineError
from repositories.ingest_batch_repository import (
    DuplicateBatchError,
    IngestBatchRecord,
    IngestBatchRepository,
)

SAMPLE_CSV_CONTENT = """session_key,try_seq,terminal_key,merchant_key,category_id,category_title,amount,adjusted_fee,session_status,try_status,switch_response_code,psp_code,issuer_bank_code,payer_card_key,verify_type,init_time_ms,verify_time_ms,created_at,try_created_at,verified_at,settled_at,expire_in
1001,1,T10,M215,CAT1,Tech,10000000,100000,Verified,Verified,PSP-05:00,PSP-05,MELLAT,CARD1,Automated,150,50,2026-08-20 12:00:00,2026-08-20 12:00:05,2026-08-20 12:00:10,2026-08-20 12:00:15,2026-08-20 12:30:00
1002,1,T10,M215,CAT1,Tech,5000000,50000,Failed,Failed,PSP-05:56,PSP-05,MELLAT,CARD2,Manual,200,50,2026-08-20 13:00:00,2026-08-20 13:00:05,,,2026-08-20 13:30:00
"""

INVALID_CSV_CONTENT = """session_key,try_seq,terminal_key,merchant_key,category_id,category_title,amount,adjusted_fee,session_status,try_status,switch_response_code,psp_code,issuer_bank_code,payer_card_key,verify_type,init_time_ms,verify_time_ms,created_at,try_created_at,verified_at,settled_at,expire_in
1001,1,T10,M215,CAT1,Tech,10000000,100000,Verified,Verified,INVALID_SWITCH_CODE,PSP-05,MELLAT,CARD1,Automated,150,50,2026-08-20 12:00:00,2026-08-20 12:00:05,2026-08-20 12:00:10,2026-08-20 12:00:15,2026-08-20 12:30:00
"""


def test_sha256_computation() -> None:
    pipeline = CSVIngestionPipeline(ch_client=MagicMock(), batch_repo=MagicMock())
    sha, raw = pipeline.compute_sha256(SAMPLE_CSV_CONTENT.encode("utf-8"))

    assert len(sha) == 64
    assert raw == SAMPLE_CSV_CONTENT.encode("utf-8")


def test_duplicate_batch_rejection() -> None:
    mock_ch = MagicMock()
    mock_repo = MagicMock(spec=IngestBatchRepository)

    batch_id = uuid.uuid4()
    existing_record = IngestBatchRecord(
        id=batch_id,
        batch_key="existing_key",
        status="committed",
        row_count=2,
        committed_at=None,
    )
    mock_repo.create_batch.side_effect = DuplicateBatchError("Duplicate batch")
    mock_repo.get_by_key.return_value = existing_record

    pipeline = CSVIngestionPipeline(ch_client=mock_ch, batch_repo=mock_repo)
    result = pipeline.ingest_file(SAMPLE_CSV_CONTENT.encode("utf-8"))

    assert result.batch_id == batch_id
    assert result.status == "committed"
    # Should not insert into ClickHouse when duplicate
    mock_ch.insert_json_rows.assert_not_called()
    mock_ch.execute_statement.assert_not_called()


def test_successful_ingestion_pipeline_flow() -> None:
    mock_ch = MagicMock()
    mock_repo = MagicMock(spec=IngestBatchRepository)

    batch_id = uuid.uuid4()
    mock_repo.create_batch.return_value = IngestBatchRecord(
        id=batch_id,
        batch_key="test_key",
        status="staging",
        row_count=0,
        committed_at=None,
    )

    pipeline = CSVIngestionPipeline(ch_client=mock_ch, batch_repo=mock_repo)
    result = pipeline.ingest_file(SAMPLE_CSV_CONTENT.encode("utf-8"))

    assert result.status == "committed"
    assert result.row_count == 2
    assert result.batch_id == batch_id

    # Check staging insert was called
    mock_ch.insert_json_rows.assert_called_once()
    table_arg, rows_arg = mock_ch.insert_json_rows.call_args[0]
    assert table_arg == "tx_staging"
    assert len(rows_arg) == 2
    assert rows_arg[0]["ingest_batch_id"] == str(batch_id)

    # Check promotion SQL executed
    mock_ch.execute_statement.assert_called_once()
    assert "INSERT INTO tx_raw" in mock_ch.execute_statement.call_args[0][0]
    assert f"WHERE ingest_batch_id = '{batch_id}'" in mock_ch.execute_statement.call_args[0][0]

    # Check repo updated to committed
    mock_repo.update_status.assert_called_once()
    call_kwargs = mock_repo.update_status.call_args[1]
    assert call_kwargs["batch_id"] == batch_id
    assert call_kwargs["status"] == "committed"
    assert call_kwargs["row_count"] == 2


def test_failed_validation_marks_batch_failed_and_leaves_raw_untouched() -> None:
    mock_ch = MagicMock()
    mock_repo = MagicMock(spec=IngestBatchRepository)

    batch_id = uuid.uuid4()
    mock_repo.create_batch.return_value = IngestBatchRecord(
        id=batch_id,
        batch_key="test_key_fail",
        status="staging",
        row_count=0,
        committed_at=None,
    )

    pipeline = CSVIngestionPipeline(ch_client=mock_ch, batch_repo=mock_repo)

    with pytest.raises(IngestionPipelineError) as exc:
        pipeline.ingest_file(INVALID_CSV_CONTENT.encode("utf-8"))

    assert "Validation failed" in str(exc.value)

    # Staging & Raw promotions should NOT have been performed
    mock_ch.insert_json_rows.assert_not_called()
    mock_ch.execute_statement.assert_not_called()

    # Batch must be marked as 'failed'
    mock_repo.update_status.assert_called_once_with(
        batch_id=batch_id,
        status="failed",
        row_count=0,
    )
