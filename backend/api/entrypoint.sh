#!/bin/sh
set -e

python manage.py migrate --noinput

case "$1" in
  prod)
    # Prod: gunicorn supervising uvicorn ASGI workers (process management,
    # graceful restarts). SSE-capable via the UvicornWorker class.
    exec gunicorn config.asgi:application \
      --worker-class uvicorn_worker.UvicornWorker \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-2}" \
      --timeout 120
    ;;
  *)
    # Dev: bare uvicorn with autoreload — simplest SSE-capable ASGI server.
    exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
    ;;
esac
