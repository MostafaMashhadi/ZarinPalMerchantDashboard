"""CohortRetentionAnalysisStrategy — retention curve analysis (§7.5).

Cohort = distinct payer_card_key values (scoped to this merchant only —
never compared across merchants per §2.2) with a successful (Verified/Paid)
session in the cohort period, segmented by verify_type.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from shared.dtos import AnalysisParams, AnalysisResult, ProvenanceSpec

from repositories.transaction_repository import TransactionRepository


class CohortRetentionAnalysisStrategy:
    """Analysis strategy that computes cohort retention curves (§7.5).

    Implements the AnalysisStrategy protocol (shared/protocols.py).

    Output is a full retention curve (AnalysisResult.series), never a
    single scalar (§7.5 step 3).
    """

    kind = "cohort_retention"

    def __init__(self, *, repo: TransactionRepository | None = None) -> None:
        self._repo = repo or TransactionRepository()

    def compute(self, merchant_id: UUID, params: AnalysisParams) -> AnalysisResult:
        period_start: datetime = params.period_start
        period_end: datetime = params.period_end
        granularity = params.extra.get("granularity", "week")
        retention_end = period_end + timedelta(days=90)

        raw_retention = self._repo.get_cohort_retention(
            merchant_id=merchant_id,
            cohort_start=period_start,
            cohort_end=period_end,
            retention_end=retention_end,
            granularity=granularity,
        )

        cohort_size = self._extract_cohort_size(raw_retention)

        series: list[dict[str, Any]] = []
        for row in raw_retention:
            retained = int(row.get("retained_users", 0))
            retention_rate = round(retained / cohort_size, 4) if cohort_size > 0 else 0.0

            bucket = row.get("bucket")
            if isinstance(bucket, str):
                bucket_str = bucket
            elif bucket is not None:
                bucket_str = str(bucket)
            else:
                bucket_str = ""

            series.append({
                "bucket": bucket_str,
                "verify_type": row.get("verify_type", ""),
                "retained_users": retained,
                "cohort_size": cohort_size,
                "retention_rate": retention_rate,
            })

        if cohort_size > 0:
            final_rate = series[-1]["retention_rate"] if series else 0.0
            headline = (
                f"Cohort of {cohort_size:,} payer cards "
                f"retained at {final_rate:.1%} after "
                f"{'week' if granularity == 'week' else 'month'} "
                f"buckets (segmented by verify_type)"
            )
        else:
            headline = "No cohort data available for the requested period."

        body: dict[str, Any] = {
            "cohort_size": cohort_size,
            "granularity": granularity,
            "retention_rates": [s["retention_rate"] for s in series],
            "segments": {
                seg: {
                    "retention_rates": [
                        s["retention_rate"] for s in series if s["verify_type"] == seg
                    ],
                }
                for seg in self._unique_verify_types(series)
            },
        }

        provenance = self.required_provenance()

        return AnalysisResult(
            kind=self.kind,
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            headline=headline,
            body=body,
            series=tuple(series),
            provenance=provenance,
        )

    @staticmethod
    def _extract_cohort_size(rows: list[dict[str, Any]]) -> int:
        for row in rows:
            size = row.get("cohort_size")
            if size is not None and int(size) > 0:
                return int(size)
        return 0

    @staticmethod
    def _unique_verify_types(series: list[dict[str, Any]]) -> list[str]:
        seen: list[str] = []
        for entry in series:
            vt = entry.get("verify_type", "")
            if vt not in seen:
                seen.append(vt)
        return seen

    def required_provenance(self) -> list[ProvenanceSpec]:
        """Returns exactly 2 ProvenanceSpec entries (§7.5).

        sequence=1: cohort definition query (distinct payer_card_key)
        sequence=2: retention bucket query (fraction retained per period)
        """
        cohort_sql = """
            SELECT DISTINCT payer_card_key
            FROM tx_raw
            WHERE merchant_key = {merchant_key:String}
              AND created_at >= {cohort_start:Date}
              AND created_at < {cohort_end:Date}
              AND session_status IN ('Verified', 'Paid')
        """

        retention_sql = """
            SELECT
                {bucket_expr} AS bucket,
                verify_type,
                count(DISTINCT payer_card_key) AS retained_users,
                (SELECT count() FROM cohort) AS cohort_size
            FROM tx_raw
            WHERE merchant_key = {merchant_key:String}
              AND created_at >= {cohort_start:Date}
              AND created_at < {retention_end:Date}
              AND session_status IN ('Verified', 'Paid')
              AND payer_card_key IN (SELECT payer_card_key FROM cohort)
            GROUP BY bucket, verify_type
            ORDER BY bucket, verify_type
        """

        return [
            ProvenanceSpec(
                source_query_id="ch.tx_raw.cohort_definition",
                clickhouse_sql=cohort_sql,
                query_params={
                    "merchant_key": "resolved-from-uuid",
                    "cohort_start": "period_start",
                    "cohort_end": "period_end",
                },
description=(
                    "Cohort definition: distinct payer_card_key with successful "
                    "session in cohort period (merchant-scoped only)"
                ),
            ),
            ProvenanceSpec(
                source_query_id="ch.tx_raw.cohort_retention_curve",
                clickhouse_sql=retention_sql,
                query_params={
                    "merchant_key": "resolved-from-uuid",
                    "cohort_start": "period_start",
                    "retention_end": "retention_end",
                    "bucket_expr": "granularity-dependent",
                },
description=(
                    "Retention curve: fraction of cohort with at least one more "
                    "successful session per period bucket, segmented by verify_type"
                ),
            ),
        ]


__all__ = ["CohortRetentionAnalysisStrategy"]
