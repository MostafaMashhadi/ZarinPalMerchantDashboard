# temporal-worker

Agentic workflow worker built on `backend/shared`.

## Setup

```bash
pip install -e ../shared
pip install temporalio
```

## Task Queues (Bulkhead, §6)

Four isolated Temporal task queues:

| Queue | Purpose | Activities |
|---|---|---|
| `analysis-queue` | Classical analysis (future use) | — (synchronous API path today) |
| `agent-queue` | InsightGenerationWorkflow | All 6 activities |
| `notification-queue` | Event dispatch (future use) | — |
| `chat-queue` | Chat memory consolidation (Task 3.7) | — (reserved) |

Each queue is a separate Temporal task queue — backlogging one cannot block others.

## Workflow

`InsightGenerationWorkflow` (run on `agent-queue`):

1. `FetchMetrics` — 30s timeout, 10s heartbeat, 3 attempts
2. `SegmentData` — 30s timeout, 10s heartbeat, 3 attempts
3. `DetectCandidateInsights` — 30s timeout, 10s heartbeat, 3 attempts
4. `RankByNovelty` — 30s timeout, 10s heartbeat, 3 attempts
5. `DraftNarrative` — 60s timeout, 5 attempts, exponential backoff, cost-checked
6. `ValidateAgainstData` — 60s timeout, 5 attempts, exponential backoff, cost-checked
7. `Publish` — 15s timeout, 3 attempts, DB commit before event dispatch

**Workflow ID:** `{merchant_id}:{period}:{kind}` — deterministic, enables deduplication.

## Cost Ledger (§6.5, §9.3)

`CostLedger` Singleton with `agent` and `chat` scopes. Checked before `DraftNarrative` and `ValidateAgainstData` calls (scope `"agent"`). Configured via environment variables:

- `LLM_AGENT_PER_RUN_CEILING_USD` (default: 0.50)
- `LLM_AGENT_MERCHANT_DAILY_CEILING_USD` (default: 5.00)
- `LLM_AGENT_GLOBAL_DAILY_CEILING_USD` (default: 50.00)

## Event Bus (§6.4, §9.5)

`InsightEventBus` — synchronous Observer dispatch. `Publish` activity uses `transaction.on_commit()` to guarantee the `InsightPublishedEvent` is dispatched only after the DB write commits.

## Running

```bash
python -m temporal_worker.main
```

## Testing

```bash
PYTHONPATH="shared:temporal-worker:../api" python -m pytest tests/ -v -p no:django
```
