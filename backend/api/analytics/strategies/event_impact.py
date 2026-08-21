"""EventImpactAnalysisStrategy — difference-in-differences analysis (§7.4).

Resolves event window from EVENT_CALENDAR, selects a matched control window,
and computes the diff-in-diff estimator isolating merchant-specific lift
from category-wide seasonal effects.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from shared.dtos import AnalysisParams, AnalysisResult, ProvenanceSpec

from repositories.transaction_repository import TransactionRepository


class EventImpactAnalysisStrategy:
    """Analysis strategy that measures event-driven lift via diff-in-diff (§7.4).

    Implements the AnalysisStrategy protocol (shared/protocols.py).
    """

    kind = "event_impact"

    _CONTROL_SEARCH_WEEKS = 8

    def __init__(self, *, repo: TransactionRepository | None = None) -> None:
        self._repo = repo or TransactionRepository()

    def compute(self, merchant_id: UUID, params: AnalysisParams) -> AnalysisResult:
        period_start: datetime = params.period_start
        period_end: datetime = params.period_end

        events = self._repo.get_events_in_range(period_start, period_end)
        if not events:
            return self._empty_result(merchant_id, period_start, period_end)

        event = events[0]
        event_start = datetime.combine(
            date.fromisoformat(event["start_date"]) if isinstance(event["start_date"], str)
            else event["start_date"],
            datetime.min.time(),
        )
        event_end = datetime.combine(
            date.fromisoformat(event["end_date"]) if isinstance(event["end_date"], str)
            else event["end_date"],
            datetime.max.time(),
        )

        control_info = self._find_control_window(event_start, event_end)
        control_quality = control_info["quality"]

        merchant_event_vol = self._repo.get_merchant_gross_volume(
            merchant_id=merchant_id,
            period_start=event_start,
            period_end=event_end,
        )
        merchant_control_vol = self._repo.get_merchant_gross_volume(
            merchant_id=merchant_id,
            period_start=control_info["start"],
            period_end=control_info["end"],
        )

        merchant = self._repo._resolve_merchant(merchant_id)
        category_id = merchant.category.category_key

        category_event_vol = self._repo.get_category_gross_volume(
            category_id=category_id,
            period_start=event_start,
            period_end=event_end,
        )
        category_control_vol = self._repo.get_category_gross_volume(
            category_id=category_id,
            period_start=control_info["start"],
            period_end=control_info["end"],
        )

        merchant_delta = merchant_event_vol - merchant_control_vol
        category_delta = category_event_vol - category_control_vol
        diff_in_diff = merchant_delta - category_delta

        pct_lift = (
            round((diff_in_diff / merchant_control_vol) * 100, 2)
            if merchant_control_vol > 0
            else 0.0
        )

        headline = (
            f"Event '{event['title']}' produced "
            f"{pct_lift:+.1f}% lift over control period "
            f"(diff-in-diff: {diff_in_diff:,} IRR)"
        )

        body: dict[str, Any] = {
            "event_key": event["event_key"],
            "event_title": event["title"],
            "event_type": event["event_type"],
            "event_window_start": event_start.isoformat(),
            "event_window_end": event_end.isoformat(),
            "control_window_start": control_info["start"].isoformat(),
            "control_window_end": control_info["end"].isoformat(),
            "control_window_quality": control_quality,
            "merchant_event_volume": merchant_event_vol,
            "merchant_control_volume": merchant_control_vol,
            "merchant_delta": merchant_delta,
            "category_event_volume": category_event_vol,
            "category_control_volume": category_control_vol,
            "category_delta": category_delta,
            "diff_in_diff": diff_in_diff,
            "pct_lift": pct_lift,
        }

        provenance = self.required_provenance()

        return AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline=headline,
            body=body,
            series=(),
            provenance=provenance,
        )

    def _find_control_window(
        self, event_start: datetime, event_end: datetime
    ) -> dict[str, Any]:
        """Find a matched control window (§7.4 step 2).

        Same weekday-of-month, same length, nearest prior non-overlapping period.
        Search backward up to 8 weeks. If none found, fall back to the same
        period one year prior.
        """
        event_length = event_end - event_start

        existing_events = self._repo.get_events_in_range(
            event_start - timedelta(weeks=self._CONTROL_SEARCH_WEEKS * 2),
            event_start,
        )
        event_dates = {
            (
                datetime.combine(
                    date.fromisoformat(e["start_date"]) if isinstance(e["start_date"], str)
                    else e["start_date"],
                    datetime.min.time(),
                ),
                datetime.combine(
                    date.fromisoformat(e["end_date"]) if isinstance(e["end_date"], str)
                    else e["end_date"],
                    datetime.max.time(),
                ),
            )
            for e in existing_events
        }

        # Compute same weekday-of-month in prior periods
        candidate_start = event_start - event_length
        for _ in range(self._CONTROL_SEARCH_WEEKS):
            candidate_end = candidate_start + event_length

            # Check if candidate overlaps any existing event
            overlaps = any(
                candidate_start <= ev_end and candidate_end >= ev_start
                for ev_start, ev_end in event_dates
            )

            if not overlaps and candidate_end <= event_start:
                return {
                    "start": candidate_start,
                    "end": candidate_end,
                    "quality": "matched",
                }

            candidate_start = candidate_start - timedelta(weeks=1)

        # Yearly fallback
        yearly_start = event_start - timedelta(days=365)
        yearly_end = yearly_start + event_length
        return {
            "start": yearly_start,
            "end": yearly_end,
            "quality": "yearly_fallback",
        }

    def _empty_result(
        self, merchant_id: UUID, period_start: datetime, period_end: datetime
    ) -> AnalysisResult:
        return AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline="No calendar events found for the requested period.",
            body={"events_found": 0},
            series=(),
            provenance=self.required_provenance(),
        )

    def required_provenance(self) -> list[ProvenanceSpec]:
        """Always returns exactly 2 ProvenanceSpec entries (§7.4 step 4, §8).

        sequence=1: merchant's event-window rollup query
        sequence=2: control-window rollup query
        """
        event_sql = """
            SELECT
                merchant_key,
                sumMerge(gross_volume_state) AS gross_volume
            FROM tx_daily_rollup
            WHERE merchant_key = {merchant_key:String}
              AND day BETWEEN {event_start:Date} AND {event_end:Date}
            GROUP BY merchant_key
        """

        control_sql = """
            SELECT
                merchant_key,
                sumMerge(gross_volume_state) AS gross_volume
            FROM tx_daily_rollup
            WHERE merchant_key = {merchant_key:String}
              AND day BETWEEN {control_start:Date} AND {control_end:Date}
            GROUP BY merchant_key
        """

        return [
            ProvenanceSpec(
                source_query_id="ch.tx_daily_rollup.event_window",
                clickhouse_sql=event_sql,
                query_params={
                    "merchant_key": "resolved-from-uuid",
                    "event_start": "event_window_start",
                    "event_end": "event_window_end",
                },
                description=(
                    "Merchant's gross volume during the event window "
                    "(diff-in-diff numerator, half 1)"
                ),
            ),
            ProvenanceSpec(
                source_query_id="ch.tx_daily_rollup.control_window",
                clickhouse_sql=control_sql,
                query_params={
                    "merchant_key": "resolved-from-uuid",
                    "control_start": "control_window_start",
                    "control_end": "control_window_end",
                },
                description=(
                    "Merchant's gross volume during the matched control window "
                    "(diff-in-diff numerator, half 2)"
                ),
            ),
        ]


__all__ = ["EventImpactAnalysisStrategy"]
