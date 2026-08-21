"""Root-level pytest conftest — set env defaults before Django settings load.

Pytest-django initializes Django settings during conftest loading,
which happens before tests/conftest.py. This root conftest ensures
env defaults are set early.
"""

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
