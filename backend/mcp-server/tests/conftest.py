"""conftest for MCP server tests.

Ensures `api/` and `backend/` directories are on sys.path so that
shared packages and facades can be imported, and sets up Django.
"""

from __future__ import annotations

import os
import sys

backend_dir = os.path.join(
    os.path.dirname(__file__), "..", ".."
)
api_dir = os.path.join(backend_dir, "api")

for p in (backend_dir, api_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "config.settings.dev"
)
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

import django  # noqa: E402

django.setup()
