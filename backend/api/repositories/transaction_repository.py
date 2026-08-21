<<<<<<< HEAD
"""Transaction data-access gateway — the only layer that talks to ClickHouse (§7.3)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any
from uuid import UUID

from django.conf import settings

from merchants.models import Merchant


class ClickHouseError(Exception):
    """Raised when a ClickHouse query fails."""


class TransactionRepository:
    """Read path for transaction rollups from ClickHouse (§5.4, §7.3).

    All reads go through the tx_daily_rollup AggregatingMergeTree using
    the mandatory -Merge pattern (§5.4). The repository resolves the
    internal merchant UUID to the merchant_key string used in ClickHouse.
    """

    def __init__(self) -> None:
        self._url: str | None = None

    def _clickhouse_url(self) -> str:
        if self._url is not None:
            return self._url
        host = settings.CLICKHOUSE_HOST or "localhost"
        port = settings.CLICKHOUSE_HTTP_PORT
        db = settings.CLICKHOUSE_DB
        self._url = f"http://{host}:{port}/?database={db}&query_format=JSONEachRow"
        return self._url

    def _resolve_merchant_key(self, merchant_id: UUID) -> str:
        """Resolve internal merchant UUID to the ClickHouse merchant_key string."""
        try:
            merchant = Merchant.objects.select_related("category").get(pk=merchant_id)
        except Merchant.DoesNotExist as exc:
            raise ClickHouseError(f"Merchant not found: {merchant_id}") from exc
        return merchant.merchant_key

    def _query_clickhouse(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a SQL query against ClickHouse HTTP interface using urllib."""
        params = params or {}
        url = self._clickhouse_url()
        query = sql
        for key, value in params.items():
            if isinstance(value, (str, int, float, bool)):
                query = query.replace(f"{{{key}}}", str(value))
            elif isinstance(value, UUID):
                query = query.replace(f"{{{key}}}", f"'{value}'")
            elif isinstance(value, (datetime, date)):
                query = query.replace(f"{{{key}}}", f"'{value.strftime('%Y-%m-%d')}'")
            else:
                query = query.replace(f"{{{key}}}", f"'{value}'")

        full_url = f"{url}&query={urllib.parse.quote(query)}"
        auth = settings.CLICKHOUSE_USER
        password = settings.CLICKHOUSE_PASSWORD
        req = urllib.request.Request(full_url)
        if auth and password:
            import base64
            credentials = base64.b64encode(f"{auth}:{password}".encode()).decode()
            req.add_header("Authorization", f"Basic {credentials}")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status != 200:
                    raise ClickHouseError(f"CH query failed: HTTP {response.status}")
                data = response.read().decode("utf-8")
                rows: list[dict[str, Any]] = []
                for line in data.strip().split("\n"):
                    if line:
                        rows.append(json.loads(line))
                return rows
        except urllib.error.URLError as exc:
            raise ClickHouseError(f"ClickHouse connection error: {exc}") from exc

    def get_merchant_summary(
        self,
        merchant_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Aggregate daily rollups for a merchant over a date range using the -Merge pattern.

        Returns a single-row dict with sessions_started, sessions_succeeded,
        gross_volume, gross_fee_proxy, abandoned_before_attempt, p50_init_ms,
        p95_init_ms.
        """
        merchant_key = self._resolve_merchant_key(merchant_id)

        sql = """
            SELECT
                merchant_key,
                sum(day_sessions) AS sessions_started,
                sum(day_succeeded) AS sessions_succeeded,
                sum(day_reversed) AS sessions_reversed,
                sum(day_gross_volume) AS gross_volume,
                sum(day_gross_fee) AS gross_fee_proxy,
                sum(day_abandoned) AS abandoned_before_attempt,
                sum(day_p50_init) AS p50_init_ms,
                sum(day_p95_init) AS p95_init_ms
            FROM (
                SELECT
                    merchant_key,
                    day,
                    uniqExactMerge(sessions_started_state) AS day_sessions,
                    uniqExactIfMerge(sessions_succeeded_state) AS day_succeeded,
                    uniqExactIfMerge(sessions_reversed_state) AS day_reversed,
                    sumMerge(gross_volume_state) AS day_gross_volume,
                    sumMerge(gross_fee_proxy_state) AS day_gross_fee,
                    countIfMerge(abandoned_before_attempt_state) AS day_abandoned,
                    quantileTimingMerge(p50_init_ms_state) AS day_p50_init,
                    quantileTimingMerge(p95_init_ms_state) AS day_p95_init
                FROM tx_daily_rollup
                WHERE merchant_key = '{merchant_key}'
                  AND day BETWEEN '{start_date}' AND '{end_date}'
                GROUP BY merchant_key, day
            )
            GROUP BY merchant_key
        """

        sql = sql.format(
            merchant_key=merchant_key,
            start_date=period_start.strftime("%Y-%m-%d"),
            end_date=period_end.strftime("%Y-%m-%d"),
        )
        rows = self._query_clickhouse(sql)
        if not rows:
            return {
                "sessions_started": 0,
                "sessions_succeeded": 0,
                "sessions_reversed": 0,
                "gross_volume": 0,
                "gross_fee_proxy": 0,
                "abandoned_before_attempt": 0,
                "p50_init_ms": 0,
                "p95_init_ms": 0,
            }
        return rows[0]

    def get_merchant_daily_series(
        self,
        merchant_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict[str, Any]]:
        """Return per-day rollup rows for a merchant over a date range using -Merge."""
        merchant_key = self._resolve_merchant_key(merchant_id)

        sql = """
            SELECT
                merchant_key,
                day,
                uniqExactMerge(sessions_started_state) AS sessions_started,
                uniqExactIfMerge(sessions_succeeded_state) AS sessions_succeeded,
                uniqExactIfMerge(sessions_reversed_state) AS sessions_reversed,
                sumMerge(gross_volume_state) AS gross_volume,
                sumMerge(gross_fee_proxy_state) AS gross_fee_proxy,
                countIfMerge(abandoned_before_attempt_state) AS abandoned_before_attempt,
                quantileTimingMerge(p50_init_ms_state) AS p50_init_ms,
                quantileTimingMerge(p95_init_ms_state) AS p95_init_ms
            FROM tx_daily_rollup
            WHERE merchant_key = '{merchant_key}'
              AND day BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY merchant_key, day
            ORDER BY day
        """

        sql = sql.format(
            merchant_key=merchant_key,
            start_date=period_start.strftime("%Y-%m-%d"),
            end_date=period_end.strftime("%Y-%m-%d"),
        )
        return self._query_clickhouse(sql)

    def get_category_summary(
        self,
        category_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Aggregate daily category rollups using -Merge pattern."""
        sql = """
            SELECT
                category_id,
                sumMerge(category_sessions_state) AS category_sessions,
                sumMerge(category_gross_volume_state) AS category_gross_volume,
                uniqExactMerge(active_merchants_state) AS active_merchants,
                avgMerge(category_avg_ticket_state) AS category_avg_ticket,
                quantileMerge(category_median_ticket_state) AS category_median_ticket,
                quantileMerge(category_p90_ticket_state) AS category_p90_ticket,
                quantileMerge(category_p95_ticket_state) AS category_p95_ticket
            FROM category_daily_rollup
            WHERE category_id = '{category_id}'
              AND day BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY category_id
        """

        sql = sql.format(
            category_id=category_id,
            start_date=period_start.strftime("%Y-%m-%d"),
            end_date=period_end.strftime("%Y-%m-%d"),
        )
        rows = self._query_clickhouse(sql)
        if not rows:
            return {
                "category_sessions": 0,
                "category_gross_volume": 0,
                "active_merchants": 0,
                "category_avg_ticket": 0,
                "category_median_ticket": 0,
                "category_p90_ticket": 0,
                "category_p95_ticket": 0,
            }
        return rows[0]

    def get_category_merchant_volumes(
        self,
        category_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> list[tuple[str, int]]:
        """Return (merchant_key, gross_volume) for all merchants in a category.

        Used by PeerComparisonAnalysisStrategy for decile ranking.
        """
        sql = """
            SELECT merchant_key, sumMerge(gross_volume_state) AS gross_volume
            FROM tx_daily_rollup
            JOIN merchant ON tx_daily_rollup.merchant_key = merchant.merchant_key
            WHERE merchant.category_id = '{category_id}'
              AND day BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY merchant_key
            ORDER BY gross_volume DESC
        """

        sql = sql.format(
            category_id=category_id,
            start_date=period_start.strftime("%Y-%m-%d"),
            end_date=period_end.strftime("%Y-%m-%d"),
        )
        rows = self._query_clickhouse(sql)
        return [(row.get("merchant_key", ""), int(row.get("gross_volume", 0))) for row in rows]

    def get_terminal_anomaly_clusters(
        self,
        merchant_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> list[dict[str, Any]]:
        """Query the terminal_noattempt_clusters materialized view using -Merge."""
        merchant_key = self._resolve_merchant_key(merchant_id)

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
            WHERE merchant_key = '{merchant_key}'
              AND bucket_start BETWEEN '{start_date}' AND '{end_date}'
            GROUP BY terminal_key, merchant_key, bucket_start, amount_bucket
            ORDER BY cluster_size DESC
        """

        sql = sql.format(
            merchant_key=merchant_key,
            start_date=period_start.strftime("%Y-%m-%d"),
            end_date=period_end.strftime("%Y-%m-%d"),
        )
        return self._query_clickhouse(sql)
=======
"""Django API wrapper / re-export for TransactionRepository."""

import sys
from pathlib import Path

# Add backend directory to sys.path if not present
backend_dir = str(Path(__file__).resolve().parent.parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from repositories.transaction_repository import TransactionRepository  # noqa: E402

__all__ = ["TransactionRepository"]
>>>>>>> 86635b79c8c983a290032777ef72e2b63964c97b
