"""Pytest bootstrap — supply local env defaults when .env is absent."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_ACCESS_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
os.environ.setdefault("POSTGRES_DB", "zarinpal")
os.environ.setdefault("POSTGRES_USER", "zarinpal")
os.environ.setdefault("POSTGRES_PASSWORD", "zarinpal")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")
os.environ.setdefault("CLICKHOUSE_HTTP_PORT", "8123")
os.environ.setdefault("CLICKHOUSE_DB", "zarinpal")
os.environ.setdefault("CLICKHOUSE_USER", "zarinpal")
os.environ.setdefault("CLICKHOUSE_PASSWORD", "zarinpal")
os.environ.setdefault("REDIS_HOST", "")
