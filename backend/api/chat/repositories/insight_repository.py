"""Insight repository — cache-aside for CHAT answer-sourcing (§9.6.1).

The ONLY place that queries Insight for freshness-based caching.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from analytics.models import Insight

FRESHNESS_WINDOWS: dict[str, timedelta] = {
    "anomaly_detection": timedelta(hours=24),
    "time_range": timedelta(hours=25),
    "peer_comparison": timedelta(hours=24),
    "event_impact": timedelta(hours=24),
    "cohort_retention": timedelta(hours=25),
}

DEFAULT_FRESHNESS_WINDOW = timedelta(hours=24)


class InsightRepository:
    """Finds fresh insights for the answer-sourcing priority (§9.6.1)."""

    def find_fresh(
        self,
        merchant_id: UUID,
        kind: str,
        period_start: datetime,
        period_end: datetime,
        *,
        freshness_window: timedelta | None = None,
    ) -> Insight | None:
        """Check if a recent Insight exists for this merchant + kind + period (§9.6.1, step a).

        Returns the Insight if it exists and is within the freshness window,
        or None if stale/no insight found.
        """
        if freshness_window is None:
            freshness_window = FRESHNESS_WINDOWS.get(
                kind, DEFAULT_FRESHNESS_WINDOW
            )

        cutoff = datetime.now(tz=period_start.tzinfo) - freshness_window

        insights = Insight.objects.filter(
            merchant_id=merchant_id,
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            generated_at__gte=cutoff,
        ).order_by("-generated_at")

        return insights.first()

    def find_any_matching(
        self,
        merchant_id: UUID,
        kind: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Insight | None:
        """Find any matching insight regardless of freshness (§9.6.1, step a fallback)."""
        return Insight.objects.filter(
            merchant_id=merchant_id,
            kind=kind,
        ).order_by("-period_start").first()

    def find_recent(
        self,
        merchant_id: UUID,
        limit: int = 10,
    ) -> list[Insight]:
        """Find recent insights for merchant (§9.6.3, memory construction)."""
        return list(
            Insight.objects.filter(
                merchant_id=merchant_id
            ).order_by("-generated_at")[:limit]
        )

    def to_dict(self, insight: Insight) -> dict[str, Any]:
        """Convert Insight model to a dict suitable for grounding/template rendering."""
        return {
            "insight_id": str(insight.id),
            "kind": insight.kind,
            "headline": insight.headline,
            "body": insight.body or {},
            "period_start": insight.period_start.isoformat() if insight.period_start else "",
            "period_end": insight.period_end.isoformat() if insight.period_end else "",
            "low_confidence_peer_set": insight.low_confidence_peer_set,
            "generated_at": insight.generated_at.isoformat() if insight.generated_at else "",
        }


__all__ = ["FRESHNESS_WINDOWS", "InsightRepository"]
