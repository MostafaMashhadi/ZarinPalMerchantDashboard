"""Agent orchestrator facade — triggers Temporal InsightGenerationWorkflow (§9.1, §9.2).

POST /api/v1/merchants/{merchant_ref}/agent/trigger-summary
GET  /api/v1/merchants/{merchant_ref}/agent/runs/{run_id}
GET  /api/v1/merchants/{merchant_ref}/agent/runs/{run_id}/cost
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from analytics.strategy_factory import AnalysisStrategyFactory
from facades.analytics_facade import AnalyticsFacade
from gateway.cost_ledger import SCOPE_AGENT, CostLedger
from repositories.transaction_repository import TransactionRepository

if TYPE_CHECKING:
    from temporalio import client as temporal_client

    from facades.authz import AuthPrincipal


class AgentOrchestrationService:
    """Orchestrates agent-run trigger and polling (§9.1, §19.6).

    On trigger: enqueues InsightGenerationWorkflow on agent-queue.
    On poll: queries Temporal workflow execution status + cost from CostLedger.
    """

    def __init__(
        self,
        *,
        facade: AnalyticsFacade | None = None,
        factory: AnalysisStrategyFactory | None = None,
        tx_repo: TransactionRepository | None = None,
        temporal_client: temporal_client.Client | None = None,
    ) -> None:
        self._facade = facade or AnalyticsFacade()
        self._factory = factory or AnalysisStrategyFactory()
        self._tx_repo = tx_repo or TransactionRepository()
        self._temporal_client = temporal_client
        self._cost_ledger = CostLedger.instance()

    def _get_temporal_client(self) -> temporal_client.Client:
        if self._temporal_client is not None:
            return self._temporal_client
        import asyncio

        from temporalio import client as temporal_client

        host = getattr(settings, "TEMPORAL_HOST", "localhost")
        port = getattr(settings, "TEMPORAL_PORT", "7233")
        return asyncio.run(temporal_client.Client.connect(f"{host}:{port}"))

    def trigger_summary(
        self,
        merchant_id: UUID,
        kind: str,
        period_start: datetime,
        period_end: datetime,
        *,
        idempotency_key: str | None = None,
        principal: AuthPrincipal | None = None,
        ingest_batch_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Trigger InsightGenerationWorkflow for a merchant's summary (§9.1, §19.6).

        Idempotency: if the same idempotency_key was already used, returns
        the existing run_id instead of creating a new workflow.
        """
        import asyncio
        import uuid as _uuid

        from workflows.insight_generation import (
            InsightGenerationWorkflow,
            WorkflowInput,
            workflow_id,
        )

        existing = self._check_idempotency(merchant_id, idempotency_key)
        if existing is not None:
            return existing

        wf_id = workflow_id(merchant_id, period_start, period_end, kind)

        input_data = WorkflowInput(
            merchant_id=merchant_id,
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            ingest_batch_id=ingest_batch_id or _uuid.uuid4(),
        )

        client = self._get_temporal_client()
        handle = asyncio.run(
            client.start_workflow(
                InsightGenerationWorkflow.run,
                input_data,
                task_queue="agent-queue",
                id=wf_id,
            )
        )

        run_id = handle.run_id
        self._store_idempotency(merchant_id, idempotency_key, run_id, wf_id)

        result: dict[str, Any] = {
            "run_id": run_id,
            "workflow_id": wf_id,
            "status": "started",
            "merchant_id": str(merchant_id),
            "kind": kind,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "created_at": timezone.now().isoformat(),
        }
        return result

    def poll_run(self, merchant_id: UUID, run_id: str) -> dict[str, Any]:
        """Poll a workflow run's status (§9.1, §19.7)."""
        import asyncio

        client = self._get_temporal_client()
        handle = client.get_workflow_handle(run_id=run_id)
        status = asyncio.run(handle.query_workflow("getStatus"))

        result: dict[str, Any] = {
            "run_id": run_id,
            "status": status,
            "merchant_id": str(merchant_id),
        }

        if status == "completed":
            try:
                insight = asyncio.run(handle.result())
                result["result"] = {
                    "kind": insight.kind,
                    "headline": insight.headline,
                    "body": insight.body,
                }
            except Exception:
                pass

        return result

    def get_run_cost(self, merchant_id: UUID, run_id: str) -> dict[str, Any]:
        """Return cost info for a run (§19.7)."""
        remaining = self._cost_ledger.remaining_merchant_budget(
            SCOPE_AGENT, str(merchant_id)
        )
        global_remaining = self._cost_ledger.remaining_global_budget(SCOPE_AGENT)

        return {
            "run_id": run_id,
            "merchant_remaining_budget": str(remaining),
            "global_remaining_budget": str(global_remaining),
            "scope": "agent",
        }

    def _check_idempotency(
        self, merchant_id: UUID, idempotency_key: str | None
    ) -> dict[str, Any] | None:
        """Check if this idempotency_key was already used (§10.2)."""
        if idempotency_key is None:
            return None
        key = f"idempotency:{merchant_id}:{idempotency_key}"
        if self._cost_ledger._redis is not None:
            try:
                existing = self._cost_ledger._redis.get(key)
                if existing:
                    data = json.loads(existing)
                    return {
                        "run_id": data["run_id"],
                        "workflow_id": data["workflow_id"],
                        "status": "running" if data.get("completed") is False else "completed",
                        "merchant_id": str(merchant_id),
                    }
            except Exception:
                pass
        return None

    def _store_idempotency(
        self,
        merchant_id: UUID,
        idempotency_key: str | None,
        run_id: str,
        workflow_id: str,
    ) -> None:
        if idempotency_key is None or self._cost_ledger._redis is None:
            return
        key = f"idempotency:{merchant_id}:{idempotency_key}"
        try:
            data = {"run_id": run_id, "workflow_id": workflow_id, "completed": False}
            self._cost_ledger._redis.setex(key, 86400, json.dumps(data))
        except Exception:
            pass



__all__ = ["AgentOrchestrationService"]
