"""conftest for temporal-worker tests.

Sets up Django for tests that need Django models (e.g. segment_data activity
that imports analytics.strategy_factory).
"""

import os
import sys

import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key-for-temporal-tests")
os.environ.setdefault("JWT_ACCESS_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "zarinpal")
os.environ.setdefault("POSTGRES_USER", "zarinpal")
os.environ.setdefault("POSTGRES_PASSWORD", "zarinpal")
os.environ.setdefault("CLICKHOUSE_HOST", "localhost")
os.environ.setdefault("CLICKHOUSE_HTTP_PORT", "8123")
os.environ.setdefault("CLICKHOUSE_DB", "zarinpal")
os.environ.setdefault("CLICKHOUSE_USER", "zarinpal")
os.environ.setdefault("CLICKHOUSE_PASSWORD", "zarinpal")
os.environ.setdefault("REDIS_HOST", "")
os.environ.setdefault("REDIS_PASSWORD", "")

try:
    django.setup()
except Exception:
    pass
