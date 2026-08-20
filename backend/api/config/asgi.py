"""ASGI entrypoint.

ASGI from day one: the chat SSE streaming endpoint (Sprint 3, §9.6) requires an
ASGI-capable server, so the runtime is uvicorn (dev) / gunicorn+uvicorn workers
(prod) and is never WSGI-only.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
