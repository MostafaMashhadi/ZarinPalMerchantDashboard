import os
import sys

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.dev"
os.environ["DJANGO_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_ACCESS_SECRET"] = "test-access-secret"
os.environ["JWT_REFRESH_SECRET"] = "test-refresh-secret"
os.environ["POSTGRES_DB"] = "zarinpal"
os.environ["POSTGRES_USER"] = "zarinpal"
os.environ["POSTGRES_PASSWORD"] = "zarinpal"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["CLICKHOUSE_HOST"] = "localhost"
os.environ["CLICKHOUSE_HTTP_PORT"] = "8123"
os.environ["CLICKHOUSE_DB"] = "zarinpal"
os.environ["CLICKHOUSE_USER"] = "zarinpal"
os.environ["CLICKHOUSE_PASSWORD"] = "zarinpal"
os.environ["REDIS_HOST"] = ""

import django

django.setup()

from django.conf import settings as dj_settings

dj_settings.DATABASES["default"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": ":memory:",
}

from django.db import connections

connections.close_all()

from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.apps import apps

loader = MigrationLoader(None, ignore_no_migrations=True)
loader.build_graph()

project_state = loader.project_state()
current_state = ProjectState.from_apps(apps)

autodetector = MigrationAutodetector(
    project_state,
    current_state,
)
changes = autodetector.changes(graph=loader.graph)
if changes:
    print("PENDING MIGRATIONS DETECTED:")
    for app_label, app_migrations in changes.items():
        print(f"  {app_label}:")
        for m in app_migrations:
            print(f"    - {m.name}")
else:
    print("No pending migrations — models and migrations are in sync")
