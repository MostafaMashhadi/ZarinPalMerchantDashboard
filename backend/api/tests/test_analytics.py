"""Tests for analytics strategies and factory."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from shared.dtos import AnalysisParams, AnalysisResult, ProvenanceSpec

from analytics.strategies.peer_comparison import PeerComparisonAnalysisStrategy
from analytics.strategies.time_range import TimeRangeAnalysisStrategy
from analytics.strategy_factory import AnalysisStrategyFactory


@pytest.fixture
def merchant_id():
    return uuid4()


@pytest.fixture
def fixed_period():
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=30)
    return start, end


@pytest.fixture
def mock_summary():
    return {
        "sessions_started": 1000,
        "sessions_succeeded": 850,
        "sessions_reversed": 10,
        "gross_volume": 50_000_000,
        "gross_fee_proxy": 2_000_000,
        "abandoned_before_attempt": 50,
        "p50_init_ms": 120,
        "p95_init_ms": 350,
    }


@pytest.fixture
def mock_daily_series():
    return [
        {
            "merchant_key": "M_TEST",
            "day": "2026-01-01",
            "sessions_started": 30,
            "sessions_succeeded": 25,
            "gross_volume": 1_000_000,
        },
        {
            "merchant_key": "M_TEST",
            "day": "2026-01-02",
            "sessions_started": 35,
            "sessions_succeeded": 30,
            "gross_volume": 1_200_000,
        },
        {
            "merchant_key": "M_TEST",
            "day": "2026-01-03",
            "sessions_started": 40,
            "sessions_succeeded": 38,
            "gross_volume": 1_500_000,
        },
    ]


@pytest.fixture
def mock_decile_info():
    return {
        "merchant_key": "M_TEST",
        "gross_volume": 5_000_000,
        "decile": 3,
        "category_id": "retail",
        "total_merchants": 100,
        "decile_count": 10,
    }


@pytest.fixture
def mock_peer_set():
    return [
        {"merchant_key": "M_A", "gross_volume": 10_000_000, "decile": 3},
        {"merchant_key": "M_TEST", "gross_volume": 5_000_000, "decile": 3},
        {"merchant_key": "M_B", "gross_volume": 4_500_000, "decile": 3},
        {"merchant_key": "M_C", "gross_volume": 4_000_000, "decile": 3},
        {"merchant_key": "M_D", "gross_volume": 3_500_000, "decile": 3},
        {"merchant_key": "M_E", "gross_volume": 3_000_000, "decile": 3},
        {"merchant_key": "M_F", "gross_volume": 2_500_000, "decile": 3},
        {"merchant_key": "M_G", "gross_volume": 2_000_000, "decile": 3},
        {"merchant_key": "M_H", "gross_volume": 1_500_000, "decile": 3},
        {"merchant_key": "M_I", "gross_volume": 1_000_000, "decile": 3},
    ]


class TestTimeRangeAnalysisStrategy:
    def test_compute_returns_analysis_result(
        self, merchant_id, fixed_period, mock_summary, mock_daily_series
    ):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_summary.return_value = mock_summary
        mock_repo.get_merchant_daily_series.return_value = mock_daily_series

        strategy = TimeRangeAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert isinstance(result, AnalysisResult)
        assert result.kind == "time_range"
        assert result.merchant_id == merchant_id
        assert result.period_start == start
        assert result.period_end == end
        assert result.headline.startswith("850 successful sessions")
        assert "gross_volume" in result.body
        assert result.body["sessions_succeeded"] == 850
        assert result.body["sessions_started"] == 1000
        assert result.body["success_rate"] == 0.85
        assert result.body["gross_volume"] == 50_000_000
        assert len(result.series) == 3

    def test_compute_with_empty_results(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_summary.return_value = {
            "sessions_started": 0,
            "sessions_succeeded": 0,
            "sessions_reversed": 0,
            "gross_volume": 0,
            "gross_fee_proxy": 0,
            "abandoned_before_attempt": 0,
            "p50_init_ms": 0,
            "p95_init_ms": 0,
        }
        mock_repo.get_merchant_daily_series.return_value = []

        strategy = TimeRangeAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["sessions_started"] == 0
        assert result.body["sessions_succeeded"] == 0
        assert result.body["success_rate"] == 0.0
        assert result.body["avg_ticket"] == 0
        assert len(result.series) == 0

    def test_compute_success_rate_calculation(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_summary.return_value = {
            "sessions_started": 200,
            "sessions_succeeded": 150,
            "sessions_reversed": 0,
            "gross_volume": 10_000_000,
            "gross_fee_proxy": 500_000,
            "abandoned_before_attempt": 20,
            "p50_init_ms": 100,
            "p95_init_ms": 300,
        }
        mock_repo.get_merchant_daily_series.return_value = []

        strategy = TimeRangeAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["success_rate"] == 0.75
        assert result.body["abandonment_rate"] == 0.1

    def test_compute_avg_ticket(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_summary.return_value = {
            "sessions_started": 100,
            "sessions_succeeded": 80,
            "sessions_reversed": 0,
            "gross_volume": 8_000_000,
            "gross_fee_proxy": 400_000,
            "abandoned_before_attempt": 5,
            "p50_init_ms": 100,
            "p95_init_ms": 300,
        }
        mock_repo.get_merchant_daily_series.return_value = []

        strategy = TimeRangeAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["avg_ticket"] == 100_000.0

    def test_required_provenance_returns_specs(self):
        strategy = TimeRangeAnalysisStrategy()
        provenance = strategy.required_provenance()

        assert len(provenance) >= 1
        assert isinstance(provenance[0], ProvenanceSpec)
        assert provenance[0].source_query_id == "ch.tx_daily_rollup.merge_summary"
        assert "uniqExactMerge" in provenance[0].clickhouse_sql

    def test_provenance_attached_to_result(
        self, merchant_id, fixed_period, mock_summary, mock_daily_series
    ):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_summary.return_value = mock_summary
        mock_repo.get_merchant_daily_series.return_value = mock_daily_series

        strategy = TimeRangeAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert len(result.provenance) >= 1
        assert isinstance(result.provenance[0], ProvenanceSpec)


class TestPeerComparisonAnalysisStrategy:
    def test_compute_returns_analysis_result(
        self, merchant_id, fixed_period, mock_decile_info, mock_peer_set
    ):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_decile.return_value = mock_decile_info
        mock_repo.get_peer_set.return_value = mock_peer_set

        strategy = PeerComparisonAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert isinstance(result, AnalysisResult)
        assert result.kind == "peer_comparison"
        assert result.merchant_id == merchant_id
        assert result.body["merchant_key"] == "M_TEST"
        assert result.body["decile"] == 3
        assert result.body["peer_set_size"] == 10
        assert result.body["merchant_gross_volume"] == 5_000_000
        assert result.low_confidence_peer_set is False
        assert len(result.series) == 10

    def test_compute_no_data_returns_empty_result(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_decile.return_value = None

        strategy = PeerComparisonAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.kind == "peer_comparison"
        assert result.body["peer_set_size"] == 0
        assert result.low_confidence_peer_set is True

    def test_compute_low_confidence_when_small_bucket(
        self, merchant_id, fixed_period, mock_decile_info
    ):
        start, end = fixed_period
        mock_decile_info_small = {
            **mock_decile_info,
            "decile_count": 5,
        }
        mock_repo = MagicMock()
        mock_repo.get_merchant_decile.return_value = mock_decile_info_small
        mock_repo.get_peer_set_range.return_value = [
            {"merchant_key": f"M_{i}", "gross_volume": 1_000_000 * i, "decile": d}
            for i, d in enumerate([3, 3, 3, 2, 4, 3])
        ]
        mock_repo.get_category_all_merchants.return_value = [
            {"merchant_key": f"M_{i}", "gross_volume": 1_000_000 * i, "decile": d}
            for i, d in enumerate([1, 1, 2, 2, 3, 3])
        ]

        strategy = PeerComparisonAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.low_confidence_peer_set is True

    def test_compute_percentile_rank(self, merchant_id, fixed_period, mock_decile_info):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_merchant_decile.return_value = mock_decile_info
        mock_repo.get_peer_set.return_value = [
            {"merchant_key": "M_A", "gross_volume": 10_000_000, "decile": 3},
            {"merchant_key": "M_TEST", "gross_volume": 5_000_000, "decile": 3},
            {"merchant_key": "M_B", "gross_volume": 4_000_000, "decile": 3},
            {"merchant_key": "M_C", "gross_volume": 3_000_000, "decile": 3},
        ]

        strategy = PeerComparisonAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["percentile_rank"] == 0.75

    def test_required_provenance_returns_exactly_two_specs(self):
        strategy = PeerComparisonAnalysisStrategy()
        provenance = strategy.required_provenance()

        assert len(provenance) == 2
        assert all(isinstance(p, ProvenanceSpec) for p in provenance)
        assert provenance[0].source_query_id == "ch.tx_daily_rollup.merchant_volume"
        assert provenance[1].source_query_id == "ch.tx_daily_rollup.category_decile_ranking"

    def test_fallback_uses_peer_set_range(
        self, merchant_id, fixed_period, mock_decile_info
    ):
        start, end = fixed_period
        mock_decile_info_small = {
            **mock_decile_info,
            "decile_count": 5,
        }
        mock_repo = MagicMock()
        mock_repo.get_merchant_decile.return_value = mock_decile_info_small
        mock_repo.get_peer_set_range.return_value = [
            {"merchant_key": f"M_{i}", "gross_volume": 1_000_000 * i, "decile": d}
            for i, d in enumerate([3, 3, 3, 2, 4, 3, 3, 2])
        ]
        mock_repo.get_category_all_merchants.return_value = []

        strategy = PeerComparisonAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        mock_repo.get_peer_set_range.assert_called_once()
        assert result.body["peer_set_size"] == 8
        assert result.low_confidence_peer_set is False

    def test_fallback_to_category_when_decile_too_small(
        self, merchant_id, fixed_period, mock_decile_info
    ):
        start, end = fixed_period
        mock_decile_info_small = {
            **mock_decile_info,
            "decile_count": 3,
        }
        mock_repo = MagicMock()
        mock_repo.get_merchant_decile.return_value = mock_decile_info_small
        mock_repo.get_peer_set_range.return_value = [
            {"merchant_key": "M_1", "gross_volume": 10_000_000, "decile": 3},
        ]
        mock_repo.get_category_all_merchants.return_value = [
            {"merchant_key": f"M_{i}", "gross_volume": 1_000_000 * i, "decile": d}
            for i, d in enumerate([1, 2, 3, 4, 5, 6, 7, 8])
        ]

        strategy = PeerComparisonAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        mock_repo.get_category_all_merchants.assert_called_once()
        assert result.body["peer_set_size"] == 8


class TestAnalysisStrategyFactory:
    def test_create_time_range_strategy(self):
        factory = AnalysisStrategyFactory()
        strategy = factory.create("time_range")

        assert isinstance(strategy, TimeRangeAnalysisStrategy)

    def test_create_peer_comparison_strategy(self):
        factory = AnalysisStrategyFactory()
        strategy = factory.create("peer_comparison")

        assert isinstance(strategy, PeerComparisonAnalysisStrategy)

    def test_create_unknown_kind_raises(self):
        factory = AnalysisStrategyFactory()
        with pytest.raises(ValueError, match="Unknown analysis kind: unknown_kind"):
            factory.create("unknown_kind")

    def test_create_not_implemented_kind_raises(self):
        factory = AnalysisStrategyFactory()
        with pytest.raises(
            NotImplementedError, match="not yet implemented"
        ):
            factory.create("cohort_retention")

    def test_factory_creates_fresh_instances(self):
        factory = AnalysisStrategyFactory()
        s1 = factory.create("time_range")
        s2 = factory.create("time_range")

        assert s1 is not s2
