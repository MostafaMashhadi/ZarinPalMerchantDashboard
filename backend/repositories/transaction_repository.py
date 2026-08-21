from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from ingestion.client import ClickHouseClient
from ingestion.config import ClickHouseConfig, default_clickhouse_config
from repositories.circuit_breaker import ClickHouseCircuitBreaker

logger = logging.getLogger(__name__)


class TransactionRepository:
    """Repository for querying ClickHouse transaction data and rollups.

    STRICT REQUIREMENT: All rollup queries MUST use the `-Merge` pattern
    against materialized views (spec §5.4, §16).
    """

    def __init__(
        self,
        client: ClickHouseClient | None = None,
        config: ClickHouseConfig | None = None,
        circuit_breaker: ClickHouseCircuitBreaker | None = None,
    ) -> None:
        self.config = config or default_clickhouse_config
        self.client = client or ClickHouseClient(self.config)
        self.circuit_breaker = circuit_breaker or ClickHouseCircuitBreaker()

    def get_daily_summary(
        self,
        merchant_key: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Fetch merchant daily summary using tx_daily_rollup with -Merge aggregation."""
        sql = """
        SELECT
            merchant_key,
            sum(day_sessions) AS sessions_started,
            sum(day_succeeded) AS sessions_succeeded,
            sum(day_reversed) AS sessions_reversed,
            sum(day_gross_volume) AS gross_volume,
            sum(day_fee_proxy) AS gross_fee_proxy,
            avg(day_avg_try_seq) AS avg_try_seq_on_success,
            sum(day_abandoned) AS abandoned_before_attempt,
            quantileTimingMerge(0.5)(p50_init_state) AS p50_init_ms,
            quantileTimingMerge(0.95)(p95_init_state) AS p95_init_ms
        FROM (
            SELECT
                merchant_key,
                day,
                uniqExactMerge(sessions_started_state) AS day_sessions,
                uniqExactIfMerge(sessions_succeeded_state) AS day_succeeded,
                uniqExactIfMerge(sessions_reversed_state) AS day_reversed,
                sumMerge(gross_volume_state) AS day_gross_volume,
                sumMerge(gross_fee_proxy_state) AS day_fee_proxy,
                avgMerge(avg_try_seq_on_success_state) AS day_avg_try_seq,
                countIfMerge(abandoned_before_attempt_state) AS day_abandoned,
                p50_init_ms_state AS p50_init_state,
                p95_init_ms_state AS p95_init_state
            FROM tx_daily_rollup
            WHERE merchant_key = %(merchant_key)s
              AND day BETWEEN %(start_date)s AND %(end_date)s
            GROUP BY merchant_key, day, p50_init_ms_state, p95_init_ms_state
        )
        GROUP BY merchant_key
        """
        params = {
            "merchant_key": merchant_key,
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
        cache_key = f"daily_summary:{merchant_key}:{start_date}:{end_date}"

        def _run_query() -> dict[str, Any]:
            rows = self.client.execute(sql, params)
            if not rows:
                return {
                    "merchant_key": merchant_key,
                    "sessions_started": 0,
                    "sessions_succeeded": 0,
                    "sessions_reversed": 0,
                    "gross_volume": 0,
                    "gross_fee_proxy": 0,
                    "avg_try_seq_on_success": 0.0,
                    "abandoned_before_attempt": 0,
                    "p50_init_ms": 0,
                    "p95_init_ms": 0,
                }
            return rows[0]

        result, _ = self.circuit_breaker.execute_with_fallback(_run_query, cache_key)
        return result

    def get_category_daily_summary(
        self,
        category_id: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Fetch category-level summary using category_daily_rollup with -Merge aggregation."""
        sql = """
        SELECT
            category_id,
            sum(day_active_merchants) AS active_merchants,
            sum(day_category_sessions) AS category_sessions,
            sum(day_gross_volume) AS category_gross_volume,
            avg(day_avg_ticket) AS category_avg_ticket,
            quantileMerge(0.5)(day_median_ticket_state) AS category_median_ticket,
            quantileMerge(0.9)(day_p90_ticket_state) AS category_p90_ticket,
            quantileMerge(0.95)(day_p95_ticket_state) AS category_p95_ticket
        FROM (
            SELECT
                category_id,
                day,
                uniqExactMerge(active_merchants_state) AS day_active_merchants,
                uniqExactMerge(category_sessions_state) AS day_category_sessions,
                sumMerge(category_gross_volume_state) AS day_gross_volume,
                avgMerge(category_avg_ticket_state) AS day_avg_ticket,
                category_median_ticket_state AS day_median_ticket_state,
                category_p90_ticket_state AS day_p90_ticket_state,
                category_p95_ticket_state AS day_p95_ticket_state
            FROM category_daily_rollup
            WHERE category_id = %(category_id)s
              AND day BETWEEN %(start_date)s AND %(end_date)s
            GROUP BY
                category_id,
                day,
                category_median_ticket_state,
                category_p90_ticket_state,
                category_p95_ticket_state
        )
        GROUP BY category_id
        """
        params = {
            "category_id": category_id,
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
        cache_key = f"category_summary:{category_id}:{start_date}:{end_date}"

        def _run_query() -> dict[str, Any]:
            rows = self.client.execute(sql, params)
            if not rows:
                return {
                    "category_id": category_id,
                    "active_merchants": 0,
                    "category_sessions": 0,
                    "category_gross_volume": 0,
                    "category_avg_ticket": 0.0,
                    "category_median_ticket": 0,
                    "category_p90_ticket": 0,
                    "category_p95_ticket": 0,
                }
            return rows[0]

        result, _ = self.circuit_breaker.execute_with_fallback(_run_query, cache_key)
        return result

    def get_merchant_peer_ranking(
        self,
        category_id: str,
        start_date: date,
        end_date: date,
        merchant_key: str,
    ) -> list[dict[str, Any]]:
        """Compute volume-decile peer rankings using window function ntile(10) inside ClickHouse."""
        sql = """
        SELECT
            merchant_key,
            total_volume,
            ntile(10) OVER (ORDER BY total_volume ASC) AS volume_decile,
            count(*) OVER () AS category_merchant_count
        FROM (
            SELECT
                merchant_key,
                sum(day_gross_volume) AS total_volume
            FROM (
                SELECT
                    merchant_key,
                    day,
                    sumMerge(gross_volume_state) AS day_gross_volume
                FROM tx_daily_rollup
                WHERE day BETWEEN %(start_date)s AND %(end_date)s
                GROUP BY merchant_key, day
            )
            GROUP BY merchant_key
            HAVING total_volume > 0
        )
        """
        params = {
            "category_id": category_id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "merchant_key": merchant_key,
        }
        return self.client.execute(sql, params)

    def get_terminal_noattempt_clusters(
        self,
        merchant_key: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Query anomaly clusters from terminal_noattempt_clusters using -Merge functions."""
        sql = """
        SELECT
            terminal_key,
            merchant_key,
            bucket_start,
            amount_bucket,
            countMerge(cluster_size_state) AS cluster_size,
            minMerge(first_seen_state) AS first_seen,
            maxMerge(last_seen_state) AS last_seen
        FROM terminal_noattempt_clusters
        WHERE merchant_key = %(merchant_key)s
          AND bucket_start >= %(start_time)s
          AND bucket_start <= %(end_time)s
        GROUP BY terminal_key, merchant_key, bucket_start, amount_bucket
        HAVING cluster_size >= 4
        ORDER BY bucket_start DESC
        """
        params = {
            "merchant_key": merchant_key,
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return self.client.execute(sql, params)

    def execute_heavy_scan(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a heavy raw query wrapped by ClickHouseCircuitBreaker (§10.3)."""
        ck = cache_key or f"heavy_scan:{hash(query)}"

        def _run() -> list[dict[str, Any]]:
            return self.client.execute(query, params, timeout=5.0)

        result, _ = self.circuit_breaker.execute_with_fallback(_run, ck)
        return result
