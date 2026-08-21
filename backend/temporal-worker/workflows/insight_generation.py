"""InsightGenerationWorkflow — Temporal durable workflow (§9.1, §9.2, §19.16).

Deterministic workflow ID: {merchant_id}:{period}:{kind}
Activities run on agent-queue (Bulkhead isolation, §9.2).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from temporalio import workflow

from activities.insight_activities import (
    DraftInput,
    FetchMetricsInput,
    PublishInput,
    ValidationInput,
    detect_candidate_insights,
    draft_narrative,
    fetch_metrics,
    publish,
    rank_by_novelty,
    segment_data,
    validate_against_data,
)
from queues import AGENT_QUEUE


@dataclass
class WorkflowInput:
    merchant_id: str
    period_start: str
    period_end: str
    kind: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowOutput:
    insight_id: str
    narrative: str
    candidates_count: int
    cost_usd: float


@workflow.defn(name="InsightGenerationWorkflow")
class InsightGenerationWorkflow:
    """Agentic insight generation workflow (§19.16).

    Activity sequence:
    1. FetchMetrics (30s, heartbeat 10s, max 3 attempts)
    2. SegmentData (30s, heartbeat 10s, max 3 attempts)
    3. DetectCandidateInsights (30s, heartbeat 10s, max 3 attempts)
    4. RankByNovelty (30s, heartbeat 10s, max 3 attempts)
    5. DraftNarrative (60s, max 5 attempts, exponential backoff, cost-checked)
    6. ValidateAgainstData (60s, max 5 attempts, exponential backoff, cost-checked)
    7. Publish (15s, max 3 attempts) — DB commit before event dispatch (§9.5)

    Crash-resume: Temporal automatically resumes from the last completed
    activity after a worker crash (§19.19).
    """

    @workflow.run
    async def run(self, input: WorkflowInput) -> WorkflowOutput:
        merchant_id = UUID(input.merchant_id)
        period_start = datetime.fromisoformat(input.period_start)
        period_end = datetime.fromisoformat(input.period_end)
        kind = input.kind

        agent_run_id = uuid.uuid4()

        metrics = await workflow.execute_activity(
            fetch_metrics,
            FetchMetricsInput(
                merchant_id=merchant_id,
                period_start=period_start,
                period_end=period_end,
            ),
            start_to_close_timeout=30,
            heartbeat_timeout=10,
            schedule_to_close_timeout=30,
            task_queue=AGENT_QUEUE.name,
        )

        segment = await workflow.execute_activity(
            segment_data,
            metrics,
            kind,
            start_to_close_timeout=30,
            heartbeat_timeout=10,
            schedule_to_close_timeout=30,
            task_queue=AGENT_QUEUE.name,
        )

        candidates = await workflow.execute_activity(
            detect_candidate_insights,
            segment,
            kind,
            start_to_close_timeout=30,
            heartbeat_timeout=10,
            schedule_to_close_timeout=30,
            task_queue=AGENT_QUEUE.name,
        )

        ranked = await workflow.execute_activity(
            rank_by_novelty,
            candidates,
            start_to_close_timeout=30,
            heartbeat_timeout=10,
            schedule_to_close_timeout=30,
            task_queue=AGENT_QUEUE.name,
        )

        draft = await workflow.execute_activity(
            draft_narrative,
            DraftInput(
                merchant_id=merchant_id,
                kind=kind,
                period_start=period_start,
                period_end=period_end,
                candidates=ranked,
                merchant_metrics=metrics.merchant_summary,
            ),
            start_to_close_timeout=60,
            schedule_to_close_timeout=60,
            task_queue=AGENT_QUEUE.name,
        )

        valid = await workflow.execute_activity(
            validate_against_data,
            ValidationInput(
                merchant_id=merchant_id,
                narrative=draft.narrative,
                claims=draft.claims,
                source_data=metrics.merchant_summary,
            ),
            start_to_close_timeout=60,
            schedule_to_close_timeout=60,
            task_queue=AGENT_QUEUE.name,
        )

        if not valid:
            raise workflow.NondeterminismError("Validation failed — insight not published")

        insight_id = await workflow.execute_activity(
            publish,
            PublishInput(
                merchant_id=merchant_id,
                kind=kind,
                period_start=period_start,
                period_end=period_end,
                narrative=draft.narrative,
                claims=draft.claims,
                candidate_insights=ranked,
                tokens_in=draft.tokens_in,
                tokens_out=draft.tokens_out,
                model_used=draft.model,
                cost_usd=draft.cost_usd,
                agent_run_step_id=agent_run_id,
            ),
            start_to_close_timeout=15,
            schedule_to_close_timeout=15,
            task_queue=AGENT_QUEUE.name,
        )

        return WorkflowOutput(
            insight_id=str(insight_id),
            narrative=draft.narrative,
            candidates_count=len(ranked),
            cost_usd=draft.cost_usd,
        )


def workflow_id(merchant_id: str, period_start: str, period_end: str, kind: str) -> str:
    """Deterministic workflow ID: {merchant_id}:{period}:{kind} (§9.2)."""
    period = f"{period_start}_{period_end}"
    return f"{merchant_id}:{period}:{kind}"


__all__ = [
    "InsightGenerationWorkflow",
    "WorkflowInput",
    "WorkflowOutput",
    "workflow_id",
]
