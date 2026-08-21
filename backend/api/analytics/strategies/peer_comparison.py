"""PeerComparisonAnalysisStrategy — volume decile peer comparison (§2.3, §7.7).

Compares a merchant against peers in the same category AND same volume decile,
with small-bucket fallback to ±1 decile or the whole category.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from shared.dtos import AnalysisParams, AnalysisResult, ProvenanceSpec

from repositories.transaction_repository import TransactionRepository


class PeerComparisonAnalysisStrategy:
    """Analysis strategy that compares a merchant to category peers by volume decile.

    Implements the AnalysisStrategy protocol (shared/protocols.py).
    """

    kind = "peer_comparison"

    _SMALL_BUCKET_THRESHOLD = 8

    def __init__(self, *, repo: TransactionRepository | None = None) -> None:
        self._repo = repo or TransactionRepository()

    def compute(self, merchant_id: UUID, params: AnalysisParams) -> AnalysisResult:
        period_start: datetime = params.period_start
        period_end: datetime = params.period_end

        decile_info = self._repo.get_merchant_decile(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )
        if decile_info is None:
            return self._empty_result(merchant_id, period_start, period_end)

        merchant_key = decile_info["merchant_key"]
        merchant_volume = int(decile_info["gross_volume"])
        decile = int(decile_info["decile"])
        category_id = decile_info["category_id"]
        decile_count = int(decile_info.get("decile_count", 0))

        peer_set = self._get_peer_set_with_fallback(
            category_id=category_id,
            decile=decile,
            merchant_key=merchant_key,
            period_start=period_start,
            period_end=period_end,
            initial_count=decile_count,
        )

        peer_volumes = [int(p["gross_volume"]) for p in peer_set]
        percentile_rank = self._compute_percentile(merchant_volume, peer_volumes)

        low_confidence = len(peer_set) < self._SMALL_BUCKET_THRESHOLD and percentile_rank > 0

        body: dict[str, Any] = {
            "merchant_key": merchant_key,
            "merchant_gross_volume": merchant_volume,
            "category": category_id,
            "decile": decile,
            "peer_set_size": len(peer_set),
            "percentile_rank": round(percentile_rank, 4),
            "peer_volumes": peer_volumes,
            "low_confidence_peer_set": low_confidence,
        }

        if percentile_rank >= 0.9:
            headline = f"Top {round((1 - percentile_rank) * 100)}% in your category by volume"
        elif percentile_rank >= 0.5:
            headline = f"Above median ({percentile_rank:.0%}) in your category by volume"
        else:
            headline = f"Bottom {round(percentile_rank * 100)}% in your category by volume"

        provenance = self.required_provenance()

        return AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline=headline,
            body=body,
            series=tuple(peer_set),
            low_confidence_peer_set=low_confidence,
            provenance=provenance,
        )

    def _get_peer_set_with_fallback(
        self,
        *,
        category_id: str,
        decile: int,
        merchant_key: str,
        period_start: datetime,
        period_end: datetime,
        initial_count: int,
    ) -> list[dict[str, Any]]:
        """Apply small-bucket fallback: decile → ±1 → category."""
        if initial_count >= self._SMALL_BUCKET_THRESHOLD:
            return self._repo.get_peer_set(
                category_id=category_id,
                decile=decile,
                period_start=period_start,
                period_end=period_end,
            )

        # Fallback 1: ±1 decile
        deciles_to_query = []
        if decile > 1:
            deciles_to_query.append(decile - 1)
        deciles_to_query.append(decile)
        if decile < 10:
            deciles_to_query.append(decile + 1)

        expanded_peerset = self._repo.get_peer_set_range(
            category_id=category_id,
            deciles=deciles_to_query,
            period_start=period_start,
            period_end=period_end,
        )

        if len(expanded_peerset) >= self._SMALL_BUCKET_THRESHOLD:
            return expanded_peerset

        # Fallback 2: entire category
        return self._repo.get_category_all_merchants(
            category_id=category_id,
            period_start=period_start,
            period_end=period_end,
        )

    @staticmethod
    def _compute_percentile(value: int, peers: list[int]) -> float:
        """Compute percentile rank of value within peers using quantileExact approach.

        Returns fraction in [0, 1] — fraction of peers with volume <= merchant volume.
        """
        if not peers:
            return 0.0
        below_or_equal = sum(1 for p in peers if p <= value)
        return below_or_equal / len(peers)

    def _empty_result(
        self, merchant_id: UUID, period_start: datetime, period_end: datetime
    ) -> AnalysisResult:
        return AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline="No transaction data available for comparison.",
            body={"sessions_started": 0, "peer_set_size": 0, "percentile_rank": 0.0},
            series=(),
            low_confidence_peer_set=True,
            provenance=self.required_provenance(),
        )

    def required_provenance(self) -> list[ProvenanceSpec]:
        """Always returns exactly 2 ProvenanceSpec entries (§7.7).

        sequence=1: merchant's own rollup query
        sequence=2: category/decile rollup query for peer comparison
        """
        merchant_sql = """
            SELECT
                merchant_key,
                sumMerge(gross_volume_state) AS gross_volume
            FROM tx_daily_rollup
            WHERE merchant_key = {merchant_key:String}
              AND day BETWEEN {start:Date} AND {end:Date}
            GROUP BY merchant_key
        """

        peer_sql = """
            SELECT
                merchant_key,
                sumMerge(gross_volume_state) AS gross_volume,
                ntile(10) OVER (ORDER BY gross_volume DESC) AS decile
            FROM (
                SELECT
                    merchant_key,
                    sumMerge(gross_volume_state) AS gross_volume
                FROM tx_daily_rollup
                WHERE category_id = {category_id:String}
                  AND day BETWEEN {start:Date} AND {end:Date}
                GROUP BY merchant_key
            )
        """

        return [
            ProvenanceSpec(
                source_query_id="ch.tx_daily_rollup.merchant_volume",
                clickhouse_sql=merchant_sql,
                query_params={
                    "merchant_key": "resolved-from-uuid",
                    "start": "period_start",
                    "end": "period_end",
                },
                description="Merchant's own gross volume rollup (excludes Reversed sessions)",
            ),
            ProvenanceSpec(
                source_query_id="ch.tx_daily_rollup.category_decile_ranking",
                clickhouse_sql=peer_sql,
                query_params={
                    "category_id": "resolved-from-merchant",
                    "start": "period_start",
                    "end": "period_end",
                },
                description=(
                    "Category decile ranking for peer set comparison "
                    "(ntile(10) window function)"
                ),
            ),
        ]


__all__ = ["PeerComparisonAnalysisStrategy"]
