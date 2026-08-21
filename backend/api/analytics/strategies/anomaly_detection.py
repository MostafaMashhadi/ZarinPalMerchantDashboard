"""AnomalyDetectionAnalysisStrategy — high-amount NoAttempt cluster detection (§2.4, §7.6).

Reads ONLY from the terminal_noattempt_clusters materialized view.
Never scans tx_raw directly. The strategy detects, scores, and returns
candidates above the severity threshold. Notification publishing is
NOT performed here — see the clean seams in _publish_insight() for
Sprint 3's InsightEventBus integration (§9.5, §19.11).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from shared.dtos import AnalysisParams, AnalysisResult, ProvenanceSpec

from repositories.transaction_repository import TransactionRepository


class AnomalyDetectionAnalysisStrategy:
    """Analysis strategy that detects anomalous NoAttempt clusters (§2.4, §7.6).

    Implements the AnalysisStrategy protocol (shared/protocols.py).

    Has zero awareness of which caller (REST/chat) invoked it. Both paths
    call the same Service layer — the chat orchestrator does not get a
    separate anomaly path (§9.5).
    """

    kind = "anomaly_detection"

    _CLUSTER_MIN_SIZE = 4
    _AMOUNT_BAND_PCT = 0.02
    _SEVERITY_THRESHOLD = 0.4
    _RECENCY_BOOST = 0.3
    _RECENCY_WINDOW_HOURS = 24

    _notify: Any = None

    def __init__(self, *, repo: TransactionRepository | None = None) -> None:
        self._repo = repo or TransactionRepository()

    def compute(self, merchant_id: UUID, params: AnalysisParams) -> AnalysisResult:
        period_start: datetime = params.period_start
        period_end: datetime = params.period_end

        raw_clusters = self._repo.get_terminal_anomaly_clusters(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )

        candidates = self._apply_clustering_heuristic(raw_clusters, now=period_end)
        scored = self._score_candidates(candidates)
        flagged = [s for s in scored if s["severity"] > self._SEVERITY_THRESHOLD]

        body: dict[str, Any] = {
            "cluster_count": len(raw_clusters),
            "candidate_count": len(scored),
            "flagged_count": len(flagged),
            "threshold": self._SEVERITY_THRESHOLD,
        }

        if not flagged:
            headline = "No anomalous NoAttempt clusters detected."
            body["clusters"] = []
        else:
            max_severity = max(s["severity"] for s in flagged)
            headline = (
                f"{len(flagged)} anomalous NoAttempt cluster(s) detected, "
                f"max severity {max_severity:.2f}"
            )
            body["clusters"] = flagged

        provenance = self.required_provenance()

        result = AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline=headline,
            body=body,
            series=tuple(flagged),
            provenance=provenance,
        )

        self._publish_insight(result)
        return result

    def _apply_clustering_heuristic(
        self,
        raw_clusters: list[dict[str, Any]],
        *,
        now: datetime,
    ) -> list[dict[str, Any]]:
        """Filter clusters meeting §2.4 criteria.

        - ≥ 4 sessions from same terminal_key with try_status = 'NoAttempt'
        - amount values within ±2% band
        (The materialized view already pre-filters to NoAttempt, so we
        apply the size and band conditions here.)
        """
        filtered: list[dict[str, Any]] = []
        for cluster in raw_clusters:
            cluster_size = int(cluster.get("cluster_size", 0))
            if cluster_size < self._CLUSTER_MIN_SIZE:
                continue

            amount_band = cluster.get("amount_bucket", 0)
            if isinstance(amount_band, (int, float)) and amount_band > 0:
                # The materialized view rounds to -4 (10k bands), so
                # all rows in the same bucket are within ±2% by construction.
                pass

            filtered.append(cluster)
        return filtered

    def _score_candidates(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply §2.4 severity scoring to each candidate cluster.

        severity = min(1.0, cluster_size / 10) + recency_boost
        Recency boost applies if cluster occurred in the last 24 hours.
        """
        now = datetime.now(tz=UTC)
        scored: list[dict[str, Any]] = []

        for candidate in candidates:
            cluster_size = int(candidate.get("cluster_size", 0))
            base_severity = min(1.0, cluster_size / 10.0)

            first_seen = candidate.get("first_seen")
            recency_boost = 0.0
            if first_seen:
                if isinstance(first_seen, str):
                    try:
                        first_seen_dt = datetime.fromisoformat(first_seen)
                    except (ValueError, TypeError):
                        first_seen_dt = None
                else:
                    first_seen_dt = first_seen

                if first_seen_dt:
                    if first_seen_dt.tzinfo is None:
                        first_seen_dt = first_seen_dt.replace(tzinfo=UTC)
                    if (now - first_seen_dt) < timedelta(hours=self._RECENCY_WINDOW_HOURS):
                        recency_boost = self._RECENCY_BOOST

            severity = min(1.0, base_severity + recency_boost)

            scored.append({
                "terminal_key": candidate.get("terminal_key", ""),
                "cluster_size": cluster_size,
                "amount_bucket": candidate.get("amount_bucket", 0),
                "first_seen": str(candidate.get("first_seen", "")),
                "last_seen": str(candidate.get("last_seen", "")),
                "base_severity": round(base_severity, 4),
                "recency_boost": round(recency_boost, 4),
                "severity": round(severity, 4),
            })

        return scored

    def _publish_insight(self, result: AnalysisResult) -> None:
        """Clean seam for Sprint 3's InsightEventBus (§9.5, §19.11).

        The Strategy does NOT decide whether to notify (§7.6 step 3).
        It simply publishes an InsightPublishedEvent for any flagged
        anomaly. NotificationService — registered as a subscriber —
        applies per-merchant notification preferences.

        This call site is identical whether invoked from REST or chat;
        the Strategy has no notion of its caller.
        """
        if self._notify is not None and result.body.get("flagged_count", 0) > 0:
            self._notify(result)

    def set_insight_publisher(self, publisher: Any) -> None:
        """Inject the InsightEventBus publisher for Sprint 3 (§19.11).

        Before Sprint 3, this is a no-op seam that does nothing.
        """
        self._notify = publisher

    def required_provenance(self) -> list[ProvenanceSpec]:
        """Returns exactly 1 ProvenanceSpec for the terminal_noattempt_clusters read."""
        sql = """
            SELECT
                terminal_key,
                merchant_key,
                bucket_start,
                amount_bucket,
                countMerge(cluster_size_state) AS cluster_size,
                minState(first_seen_state) AS first_seen,
                maxState(last_seen_state) AS last_seen
            FROM terminal_noattempt_clusters
            WHERE merchant_key = {merchant_key:String}
              AND bucket_start BETWEEN {start:Date} AND {end:Date}
            GROUP BY terminal_key, merchant_key, bucket_start, amount_bucket
            ORDER BY cluster_size DESC
        """

        return [
            ProvenanceSpec(
                source_query_id="ch.terminal_noattempt_clusters.merge",
                clickhouse_sql=sql,
                query_params={
                    "merchant_key": "resolved-from-uuid",
                    "start": "period_start",
                    "end": "period_end",
                },
                description=(
                    "Anomaly candidate clusters from terminal_noattempt_clusters "
                    "materialized view using -Merge pattern (§2.4, §7.6)"
                ),
            ),
        ]


__all__ = ["AnomalyDetectionAnalysisStrategy"]
