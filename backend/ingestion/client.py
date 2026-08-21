from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from ingestion.config import ClickHouseConfig, default_clickhouse_config

logger = logging.getLogger(__name__)


class ClickHouseError(Exception):
    """Exception raised for ClickHouse execution errors."""


class ClickHouseTimeoutError(ClickHouseError):
    """Exception raised when a ClickHouse query exceeds its timeout."""


class ClickHouseClient:
    """HTTP client for ClickHouse supporting queries, batch inserts, and DDL."""

    def __init__(self, config: ClickHouseConfig | None = None) -> None:
        self.config = config or default_clickhouse_config

    def ping(self) -> bool:
        """Check ClickHouse server availability."""
        url = f"{self.config.http_url}/ping"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200 and resp.read().strip() == b"Ok."
        except Exception as e:
            logger.warning("ClickHouse ping failed: %s", e)
            return False

    def execute(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return list of dictionaries (JSONEachRow format)."""
        clean_query = query.strip().rstrip(";")
        if "FORMAT" not in clean_query.upper():
            clean_query = f"{clean_query} FORMAT JSONEachRow"

        query_params = {
            "database": self.config.database,
            "user": self.config.user,
            "password": self.config.password,
        }
        if params:
            for k, v in params.items():
                query_params[f"param_{k}"] = str(v)

        url = f"{self.config.http_url}/?{urllib.parse.urlencode(query_params)}"
        req = urllib.request.Request(
            url,
            data=clean_query.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
                if not data.strip():
                    return []
                return [json.loads(line) for line in data.strip().split("\n") if line.strip()]
        except TimeoutError as e:
            raise ClickHouseTimeoutError(f"ClickHouse query timed out after {timeout}s: {e}") from e
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise ClickHouseError(f"ClickHouse HTTP {e.code} error: {err_msg}") from e
        except Exception as e:
            if "timed out" in str(e).lower():
                raise ClickHouseTimeoutError(f"ClickHouse query timed out: {e}") from e
            raise ClickHouseError(f"ClickHouse execution error: {e}") from e

    def execute_statement(
        self,
        statement: str,
        timeout: float = 30.0,
    ) -> None:
        """Execute a DDL or INSERT statement without returning parsed rows."""
        query_params = {
            "database": self.config.database,
            "user": self.config.user,
            "password": self.config.password,
        }
        url = f"{self.config.http_url}/?{urllib.parse.urlencode(query_params)}"
        req = urllib.request.Request(
            url,
            data=statement.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status not in (200, 204):
                    body = resp.read().decode("utf-8")
                    raise ClickHouseError(f"Statement failed with status {resp.status}: {body}")
        except TimeoutError as e:
            raise ClickHouseTimeoutError(f"ClickHouse statement timed out after {timeout}s: {e}") from e
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise ClickHouseError(f"ClickHouse HTTP {e.code} error: {err_msg}") from e
        except Exception as e:
            if "timed out" in str(e).lower():
                raise ClickHouseTimeoutError(f"ClickHouse statement timed out: {e}") from e
            raise ClickHouseError(f"ClickHouse statement error: {e}") from e

    def insert_json_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        timeout: float = 60.0,
    ) -> None:
        """Insert a list of row dicts into table using JSONEachRow format."""
        if not rows:
            return

        query_params = {
            "database": self.config.database,
            "user": self.config.user,
            "password": self.config.password,
            "query": f"INSERT INTO {table} FORMAT JSONEachRow",
        }
        url = f"{self.config.http_url}/?{urllib.parse.urlencode(query_params)}"
        body = "\n".join(json.dumps(r, default=str) for r in rows).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-ndjson; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status not in (200, 204):
                    msg = resp.read().decode("utf-8")
                    raise ClickHouseError(f"Insert failed with status {resp.status}: {msg}")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            raise ClickHouseError(f"ClickHouse insert HTTP {e.code} error: {err_msg}") from e
        except Exception as e:
            raise ClickHouseError(f"ClickHouse insert error: {e}") from e
