# api

Django + DRF service (Sprint 0.2). Also hosts chat turn-handling and SSE (§9.6);
there is no separate chat service.

## Layout

- `config/settings/` — `base.py` (shared), `dev.py`, `prod.py` (selected via
  `DJANGO_SETTINGS_MODULE`; defaults to dev).
- `config/asgi.py` — runtime entrypoint; `config/wsgi.py` kept only for tooling.
- `merchants/`, `analytics/`, `chat/` — registered apps, modeled in later tasks.
- `controllers/` — DRF APIViews/ViewSets only (no business logic).
- `facades/` — Analytics/Merchant/Agent/Notification/Chat facades (filled per domain).
- `services/`, `repositories/` — namespace packages for later tasks.
- `tests/` — pytest suite (`pytest-django`).

## Run

```bash
docker compose up api            # builds ./backend, runs migrations, serves on :8000
curl localhost:8000/api/v1/health   # -> {"status":"ok"}
```

The image installs `backend/shared` editable from `/opt/shared`; in the default
dev command both `backend/api` and `backend/shared` are bind-mounted, so code
changes hot-reload.

## ASGI server decision

ASGI from day one — chat's SSE streaming endpoint (Sprint 3) needs it and a
WSGI-only scaffold would be retrofitted later.

- **Dev: bare `uvicorn --reload`.** Simplest SSE-capable server, autoreload.
- **Prod: `gunicorn` with `uvicorn_worker.UvicornWorker`** (`command: ["prod"]`
  via `docker-compose.prod.yml`). Gunicorn adds process supervision and graceful
  worker recycling; the uvicorn worker class keeps full ASGI/SSE capability.

## Local checks (CI-equivalent)

Requires Postgres (e.g. `docker compose up -d postgres`) and a local venv:

```bash
pip install -r requirements-dev.txt && pip install -e ../shared
make check        # ruff check . + pytest  (make lint / make test individually)
```

Ruff config lives in `pyproject.toml` (`[tool.ruff]`); formatting via
`make format` (`ruff format .`).
