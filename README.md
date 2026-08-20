# ZarinPal Merchant Dashboard

Merchant-facing analytics platform: classical BI (ClickHouse rollups, peer ranking, drill-down), an agentic insight layer with grounded LLM narratives, and a conversational “Ask the Dashboard” agent that answers only from computed `AnalysisResult`s. Django + DRF, React, PostgreSQL, ClickHouse, Temporal, Redis, and AvalAI.

## Quickstart

```bash
cp .env.example .env
docker compose up
```

That starts Postgres, ClickHouse, Redis, and Temporal (`temporalio/auto-setup` with its own Postgres). Application services (`api`, `frontend`, `ingestion`) are Compose stanzas with the `app` profile and land in later sprints. Chat is not a Compose service — turn handling lives in `api`; memory consolidation lives in `temporal-worker`.

Engineering spec: [docs/spec.md](docs/spec.md).
