"""TimeRangeAnalysisStrategy — computes per-merchant time-range analysis (§7.1, §7.3).

Uses the -Merge pattern via TransactionRepository to read from the
tx_daily_rollup AggregatingMergeTree materialization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from shared.dtos import AnalysisParams, AnalysisResult, ProvenanceSpec

from repositories.transaction_repository import TransactionRepository


class TimeRangeAnalysisStrategy:
    """Analysis strategy that computes a time-range summary for a merchant.

    Implements the AnalysisStrategy protocol (shared/protocols.py).
    """

    kind = "time_range"

    def __init__(self, *, repo: TransactionRepository | None = None) -> None:
        self._repo = repo or TransactionRepository()

    def compute(self, merchant_id: UUID, params: AnalysisParams) -> AnalysisResult:
        period_start: datetime = params.period_start
        period_end: datetime = params.period_end

        summary = self._repo.get_merchant_summary(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )

        daily_series = self._repo.get_merchant_daily_series(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )

        sessions_succeeded = int(summary.get("sessions_succeeded", 0))
        sessions_started = int(summary.get("sessions_started", 0))
        gross_volume = int(summary.get("gross_volume", 0))
        gross_fee_proxy = int(summary.get("gross_fee_proxy", 0))
        abandoned = int(summary.get("abandoned_before_attempt", 0))
        p50_init_ms = float(summary.get("p50_init_ms", 0))
        p95_init_ms = float(summary.get("p95_init_ms", 0))

        success_rate = (
            round(sessions_succeeded / sessions_started, 4) if sessions_started > 0 else 0.0
        )
        abandonment_rate = (
            round(abandoned / sessions_started, 4) if sessions_started > 0 else 0.0
        )
        avg_ticket = (
            round(gross_volume / sessions_succeeded, 2) if sessions_succeeded > 0 else 0
        )

        headline = (
            f"{sessions_succeeded:,} successful sessions, "
            f"{gross_volume:,} IRR gross volume "
            f"({success_rate:.1%} success rate)"
        )

        body: dict[str, Any] = {
            "sessions_started": sessions_started,
            "sessions_succeeded": sessions_succeeded,
            "sessions_reversed": int(summary.get("sessions_reversed", 0)),
            "gross_volume": gross_volume,
            "gross_fee_proxy": gross_fee_proxy,
            "abandoned_before_attempt": abandoned,
            "success_rate": success_rate,
            "abandonment_rate": abandonment_rate,
            "avg_ticket": avg_ticket,
            "p50_init_ms": p50_init_ms,
            "p95_init_ms": p95_init_ms,
        }

        series = tuple(daily_series)

        provenance = (self._build_provenance(period_start, period_end),)

        return AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline=headline,
            body=body,
            series=series,
            provenance=provenance,
        )

    def required_provenance(self) -> list[ProvenanceSpec]:
        """Declare the provenance specs that this strategy's compute() will produce."""
        return [self._build_provenance(datetime.now(), datetime.now())]

    @staticmethod
    def _build_provenance(period_start: datetime, period_end: datetime) -> ProvenanceSpec:
        sql = """
            SELECT
                merchant_key,
                sum(day_sessions) AS sessions_started,
                sum(day_succeeded) AS sessions_succeeded,
                sum(day_gross_volume) AS gross_volume
            FROM (
                SELECT
                    merchant_key,
                    day,
                    uniqExactMerge(sessions_started_state) AS day_sessions,
                    uniqExactIfMerge(sessions_succeeded_state) AS day_succeeded,
                    sumMerge(gross_volume_state) AS day_gross_volume
                FROM tx_daily_rollup
                WHERE merchant_key = {merchant_key:String}
                  AND day BETWEEN {start:Date} AND {end:Date}
                GROUP BY merchant_key, day
            )
            GROUP BY merchant_key
        """
        return ProvenanceSpec(
            source_query_id="ch.tx_daily_rollup.merge_summary",
            clickhouse_sql=sql,
            query_params={
                "merchant_key": "resolved-from-uuid",
                "start": period_start.strftime("%Y-%m-%d"),
                "end": period_end.strftime("%Y-%m-%d"),
            },
            description="Aggregated merchant summary via -Merge pattern on tx_daily_rollup",
        )


__all__ = ["TimeRangeAnalysisStrategy"]
