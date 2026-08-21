from datetime import date, datetime
from unittest.mock import MagicMock

from repositories.circuit_breaker import ClickHouseCircuitBreaker
from repositories.transaction_repository import TransactionRepository


def test_daily_summary_uses_merge_pattern_on_rollup() -> None:
    mock_client = MagicMock()
    mock_client.execute.return_value = [{"merchant_key": "M215", "gross_volume": 1000}]
    repo = TransactionRepository(client=mock_client, circuit_breaker=ClickHouseCircuitBreaker())

    repo.get_daily_summary("M215", date(2026, 8, 1), date(2026, 8, 20))

    assert mock_client.execute.called
    sql = mock_client.execute.call_args[0][0]

    # Must target rollup table
    assert "FROM tx_daily_rollup" in sql
    # Must use -Merge aggregation combinators
    assert "uniqExactMerge(sessions_started_state)" in sql
    assert "uniqExactIfMerge(sessions_succeeded_state)" in sql
    assert "uniqExactIfMerge(sessions_reversed_state)" in sql
    assert "sumMerge(gross_volume_state)" in sql
    assert "sumMerge(gross_fee_proxy_state)" in sql
    assert "avgMerge(avg_try_seq_on_success_state)" in sql
    assert "countIfMerge(abandoned_before_attempt_state)" in sql
    assert "quantileTimingMerge(0.5)" in sql
    assert "quantileTimingMerge(0.95)" in sql


def test_category_daily_summary_uses_merge_pattern_on_rollup() -> None:
    mock_client = MagicMock()
    mock_client.execute.return_value = [{"category_id": "CAT1", "category_gross_volume": 5000}]
    repo = TransactionRepository(client=mock_client, circuit_breaker=ClickHouseCircuitBreaker())

    repo.get_category_daily_summary("CAT1", date(2026, 8, 1), date(2026, 8, 20))

    assert mock_client.execute.called
    sql = mock_client.execute.call_args[0][0]

    # Must target category rollup table
    assert "FROM category_daily_rollup" in sql
    # Must use -Merge combinators
    assert "uniqExactMerge(active_merchants_state)" in sql
    assert "uniqExactMerge(category_sessions_state)" in sql
    assert "sumMerge(category_gross_volume_state)" in sql
    assert "avgMerge(category_avg_ticket_state)" in sql
    assert "quantileMerge(0.5)" in sql
    assert "quantileMerge(0.9)" in sql
    assert "quantileMerge(0.95)" in sql


def test_peer_ranking_uses_merge_pattern_and_window_function() -> None:
    mock_client = MagicMock()
    mock_client.execute.return_value = []
    repo = TransactionRepository(client=mock_client, circuit_breaker=ClickHouseCircuitBreaker())

    repo.get_merchant_peer_ranking("CAT1", date(2026, 8, 1), date(2026, 8, 20), "M215")

    assert mock_client.execute.called
    sql = mock_client.execute.call_args[0][0]

    # Must use -Merge on tx_daily_rollup and ntile window function
    assert "sumMerge(gross_volume_state)" in sql
    assert "FROM tx_daily_rollup" in sql
    assert "ntile(10) OVER" in sql


def test_terminal_anomaly_clusters_uses_merge_pattern() -> None:
    mock_client = MagicMock()
    mock_client.execute.return_value = []
    repo = TransactionRepository(client=mock_client, circuit_breaker=ClickHouseCircuitBreaker())

    repo.get_terminal_noattempt_clusters(
        "M215",
        datetime(2026, 8, 20, 0, 0, 0),
        datetime(2026, 8, 20, 23, 59, 59),
    )

    assert mock_client.execute.called
    sql = mock_client.execute.call_args[0][0]

    assert "FROM terminal_noattempt_clusters" in sql
    assert "countMerge(cluster_size_state)" in sql
    assert "minMerge(first_seen_state)" in sql
    assert "maxMerge(last_seen_state)" in sql
