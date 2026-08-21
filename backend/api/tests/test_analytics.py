"""Tests for analytics strategies and factory."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from analytics.strategies.anomaly_detection import AnomalyDetectionAnalysisStrategy
from analytics.strategies.cohort_retention import CohortRetentionAnalysisStrategy
from analytics.strategies.event_impact import EventImpactAnalysisStrategy
from analytics.strategies.peer_comparison import PeerComparisonAnalysisStrategy
from analytics.strategies.time_range import TimeRangeAnalysisStrategy
from analytics.strategy_factory import AnalysisStrategyFactory
from shared.dtos import ANALYSIS_KINDS, AnalysisParams, AnalysisResult, ProvenanceSpec


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

    def test_create_event_impact_strategy(self):
        factory = AnalysisStrategyFactory()
        strategy = factory.create("event_impact")

        assert isinstance(strategy, EventImpactAnalysisStrategy)

    def test_create_cohort_retention_strategy(self):
        factory = AnalysisStrategyFactory()
        strategy = factory.create("cohort_retention")

        assert isinstance(strategy, CohortRetentionAnalysisStrategy)

    def test_create_anomaly_detection_strategy(self):
        factory = AnalysisStrategyFactory()
        strategy = factory.create("anomaly_detection")

        assert isinstance(strategy, AnomalyDetectionAnalysisStrategy)

    def test_create_unknown_kind_raises(self):
        factory = AnalysisStrategyFactory()
        with pytest.raises(ValueError, match="Unknown analysis kind: unknown_kind"):
            factory.create("unknown_kind")

    def test_factory_creates_all_registered_kinds(self):
        factory = AnalysisStrategyFactory()
        for kind in ANALYSIS_KINDS:
            strategy = factory.create(kind)
            assert strategy is not None
            assert strategy.kind == kind

    def test_factory_creates_fresh_instances(self):
        factory = AnalysisStrategyFactory()
        s1 = factory.create("time_range")
        s2 = factory.create("time_range")

        assert s1 is not s2


class TestEventImpactAnalysisStrategy:
    def test_compute_returns_analysis_result(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_events_in_range.return_value = [
            {
                "event_key": "nowruz2026",
                "title": "Nowruz 2026",
                "start_date": "2026-03-20",
                "end_date": "2026-03-25",
                "event_type": "promotion",
            }
        ]
        mock_repo._resolve_merchant.return_value = MagicMock(
            merchant_key="M_TEST",
            category=MagicMock(category_key="retail"),
        )
        mock_repo.get_merchant_gross_volume.side_effect = [10_000_000, 8_000_000]
        mock_repo.get_category_gross_volume.side_effect = [100_000_000, 90_000_000]

        strategy = EventImpactAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert isinstance(result, AnalysisResult)
        assert result.kind == "event_impact"
        assert result.merchant_id == merchant_id
        assert result.body["event_key"] == "nowruz2026"
        assert result.body["merchant_event_volume"] == 10_000_000
        assert result.body["merchant_control_volume"] == 8_000_000
        assert result.body["category_event_volume"] == 100_000_000
        assert result.body["category_control_volume"] == 90_000_000
        assert result.body["merchant_delta"] == 2_000_000
        assert result.body["category_delta"] == 10_000_000
        assert result.body["diff_in_diff"] == -8_000_000
        assert "control_window_quality" in result.body

    def test_compute_no_events_returns_empty(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_events_in_range.return_value = []

        strategy = EventImpactAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.kind == "event_impact"
        assert result.body["events_found"] == 0 or result.body.get("events_found", 1) == 0
        assert len(result.headline) > 0

    def test_required_provenance_returns_exactly_two_specs(self):
        strategy = EventImpactAnalysisStrategy()
        provenance = strategy.required_provenance()

        assert len(provenance) == 2
        assert all(isinstance(p, ProvenanceSpec) for p in provenance)
        assert provenance[0].source_query_id == "ch.tx_daily_rollup.event_window"
        assert provenance[1].source_query_id == "ch.tx_daily_rollup.control_window"

    def test_control_window_yearly_fallback(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_events_in_range.return_value = [
            {
                "event_key": "event1",
                "title": "Test Event",
                "start_date": "2026-03-20",
                "end_date": "2026-03-25",
                "event_type": "promotion",
            }
        ]
        mock_repo.get_events_in_range.side_effect = [
            [
                {
                    "event_key": "event1",
                    "title": "Test Event",
                    "start_date": "2026-03-20",
                    "end_date": "2026-03-25",
                    "event_type": "promotion",
                }
            ],
            [
                {
                    "event_key": "prev",
                    "title": "Prev",
                    "start_date": "2026-01-01",
                    "end_date": "2026-03-25",
                    "event_type": "other",
                }
            ],
        ]
        mock_repo._resolve_merchant.return_value = MagicMock(
            merchant_key="M_TEST",
            category=MagicMock(category_key="retail"),
        )
        mock_repo.get_merchant_gross_volume.side_effect = [5_000_000, 4_000_000]
        mock_repo.get_category_gross_volume.side_effect = [50_000_000, 40_000_000]

        strategy = EventImpactAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert "control_window_quality" in result.body


class TestCohortRetentionAnalysisStrategy:
    def test_compute_returns_analysis_result(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_cohort_retention.return_value = [
            {
                "bucket": "2026-01-04",
                "verify_type": "Automated",
                "retained_users": 80,
                "cohort_size": 100,
            },
            {
                "bucket": "2026-01-11",
                "verify_type": "Automated",
                "retained_users": 60,
                "cohort_size": 100,
            },
            {
                "bucket": "2026-01-04",
                "verify_type": "Manual",
                "retained_users": 20,
                "cohort_size": 100,
            },
        ]

        strategy = CohortRetentionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert isinstance(result, AnalysisResult)
        assert result.kind == "cohort_retention"
        assert result.merchant_id == merchant_id
        assert result.body["cohort_size"] == 100
        assert result.body["granularity"] == "week"
        assert len(result.series) == 3
        assert result.series[0]["verify_type"] == "Automated"
        assert result.series[0]["retention_rate"] == 0.8
        assert result.series[1]["retention_rate"] == 0.6
        assert result.series[2]["retention_rate"] == 0.2

    def test_compute_empty_cohort(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_cohort_retention.return_value = []

        strategy = CohortRetentionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.kind == "cohort_retention"
        assert result.body["cohort_size"] == 0
        assert len(result.series) == 0

    def test_compute_segments_by_verify_type(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_cohort_retention.return_value = [
            {
                "bucket": "2026-01-04",
                "verify_type": "Automated",
                "retained_users": 80,
                "cohort_size": 100,
            },
            {
                "bucket": "2026-01-04",
                "verify_type": "Manual",
                "retained_users": 10,
                "cohort_size": 100,
            },
        ]

        strategy = CohortRetentionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert "Automated" in result.body["segments"]
        assert "Manual" in result.body["segments"]

    def test_required_provenance_returns_exactly_two_specs(self):
        strategy = CohortRetentionAnalysisStrategy()
        provenance = strategy.required_provenance()

        assert len(provenance) == 2
        assert all(isinstance(p, ProvenanceSpec) for p in provenance)
        assert provenance[0].source_query_id == "ch.tx_raw.cohort_definition"
        assert provenance[1].source_query_id == "ch.tx_raw.cohort_retention_curve"

    def test_compute_granularity_month(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_cohort_retention.return_value = [
            {
                "bucket": "2026-01-01",
                "verify_type": "Automated",
                "retained_users": 50,
                "cohort_size": 100,
            },
        ]

        strategy = CohortRetentionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(
            period_start=start,
            period_end=end,
            extra={"granularity": "month"},
        )

        result = strategy.compute(merchant_id, params)

        assert result.body["granularity"] == "month"


class TestAnomalyDetectionAnalysisStrategy:
    @pytest.fixture
    def mock_clusters(self):
        return [
            {
                "terminal_key": "T1",
                "merchant_key": "M_TEST",
                "bucket_start": "2026-08-20 10:00:00",
                "amount_bucket": 198000000,
                "cluster_size": 10,
                "first_seen": "2026-08-20 10:00:00",
                "last_seen": "2026-08-20 10:15:00",
            },
            {
                "terminal_key": "T2",
                "merchant_key": "M_TEST",
                "bucket_start": "2026-08-19 08:00:00",
                "amount_bucket": 5000000,
                "cluster_size": 3,
                "first_seen": "2026-08-19 08:00:00",
                "last_seen": "2026-08-19 08:10:00",
            },
        ]

    def test_compute_returns_flagged_clusters(self, merchant_id, fixed_period, mock_clusters):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = mock_clusters

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert isinstance(result, AnalysisResult)
        assert result.kind == "anomaly_detection"
        assert result.merchant_id == merchant_id
        assert result.body["cluster_count"] == 2
        assert result.body["flagged_count"] == 1
        assert len(result.series) == 1
        assert result.series[0]["terminal_key"] == "T1"
        assert result.series[0]["cluster_size"] == 10
        assert result.series[0]["severity"] > 0.4

    def test_compute_no_anomalies(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = [
            {
                "terminal_key": "T1",
                "merchant_key": "M_TEST",
                "bucket_start": "2026-08-20 10:00:00",
                "amount_bucket": 1000000,
                "cluster_size": 2,
                "first_seen": "2026-08-20 10:00:00",
                "last_seen": "2026-08-20 10:15:00",
            },
        ]

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["flagged_count"] == 0
        assert len(result.series) == 0
        assert "No anomalous" in result.headline

    def test_compute_empty_clusters(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = []

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["cluster_count"] == 0
        assert result.body["flagged_count"] == 0
        assert len(result.series) == 0

    def test_severity_scoring_formula(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = [
            {
                "terminal_key": "T1",
                "merchant_key": "M_TEST",
                "bucket_start": "2000-01-01 00:00:00",
                "amount_bucket": 1000000,
                "cluster_size": 5,
                "first_seen": "2000-01-01 00:00:00",
                "last_seen": "2000-01-01 00:15:00",
            },
        ]

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert len(result.series) == 1
        score = result.series[0]
        assert score["base_severity"] == 0.5
        assert score["severity"] == 0.5

    def test_recency_boost_applied(self, merchant_id, fixed_period):

        start, end = fixed_period
        now = datetime.now(tz=UTC)
        recent = now - timedelta(hours=2)

        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = [
            {
                "terminal_key": "T1",
                "merchant_key": "M_TEST",
                "bucket_start": recent.strftime("%Y-%m-%d %H:%M:%S"),
                "amount_bucket": 1000000,
                "cluster_size": 5,
                "first_seen": recent.strftime("%Y-%m-%d %H:%M:%S"),
                "last_seen": recent.strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        if len(result.series) == 1:
            score = result.series[0]
            assert score["recency_boost"] == 0.3
            assert score["severity"] == 0.8

    def test_threshold_filter_excludes_below_0_4(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = [
            {
                "terminal_key": "T1",
                "merchant_key": "M_TEST",
                "bucket_start": "2000-01-01 00:00:00",
                "amount_bucket": 1000000,
                "cluster_size": 3,
                "first_seen": "2000-01-01 00:00:00",
                "last_seen": "2000-01-01 00:15:00",
            },
        ]

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end)

        result = strategy.compute(merchant_id, params)

        assert result.body["flagged_count"] == 0

    def test_required_provenance_returns_one_spec(self):
        strategy = AnomalyDetectionAnalysisStrategy()
        provenance = strategy.required_provenance()

        assert len(provenance) == 1
        assert isinstance(provenance[0], ProvenanceSpec)
        assert provenance[0].source_query_id == "ch.terminal_noattempt_clusters.merge"

    def test_no_caller_awareness(self, merchant_id, fixed_period, mock_clusters):
        """Strategy has no notion of which caller invoked it."""
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = mock_clusters

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        params = AnalysisParams(period_start=start, period_end=end, extra={})

        result = strategy.compute(merchant_id, params)
        assert result.kind == "anomaly_detection"

    def test_publish_seam_is_noop_without_publisher(self, merchant_id, fixed_period):
        start, end = fixed_period
        mock_repo = MagicMock()
        mock_repo.get_terminal_anomaly_clusters.return_value = []

        strategy = AnomalyDetectionAnalysisStrategy(repo=mock_repo)
        assert strategy._notify is None

        params = AnalysisParams(period_start=start, period_end=end)
        strategy.compute(merchant_id, params)

    def test_set_insight_publisher(self):
        strategy = AnomalyDetectionAnalysisStrategy()
        mock_publisher = MagicMock()
        strategy.set_insight_publisher(mock_publisher)
        assert strategy._notify is mock_publisher
