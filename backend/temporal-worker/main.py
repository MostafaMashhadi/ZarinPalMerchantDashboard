"""Temporal worker entry point — registers activities and workflows on task queues (§9.2, §19.16).

Run: python -m temporal_worker.main
"""

from __future__ import annotations

import asyncio
import os

from temporalio import worker

from activities.insight_activities import (
    detect_candidate_insights,
    draft_narrative,
    fetch_metrics,
    publish,
    rank_by_novelty,
    segment_data,
    validate_against_data,
)
from queues import (
    AGENT_QUEUE,
    CHAT_QUEUE,
    NOTIFICATION_QUEUE,
)
from workflows.insight_generation import InsightGenerationWorkflow


def _get_temporal_target() -> str:
    host = os.environ.get("TEMPORAL_HOST", "localhost")
    port = os.environ.get("TEMPORAL_PORT", "7233")
    return f"{host}:{port}"


def _get_namespace() -> str:
    return os.environ.get("TEMPORAL_NAMESPACE", "default")


async def run_worker(
    task_queue: str,
    *,
    workflows: list | None = None,
    activities: list | None = None,
) -> worker.Worker:
    """Start a Temporal worker for a specific task queue.

    Each task queue is a separate bulkhead — backlogging one does not
    affect the others (§6, §9.2).
    """
    w = worker.Worker(
        client=await _get_client(),
        workflows=workflows or [InsightGenerationWorkflow],
        activities=activities or [
            fetch_metrics,
            segment_data,
            detect_candidate_insights,
            rank_by_novelty,
            draft_narrative,
            validate_against_data,
            publish,
        ],
        task_queue=task_queue,
    )
    return w


async def _get_client():
    from temporalio import client

    return await client.Client.connect(
        _get_temporal_target(),
        namespace=_get_namespace(),
    )


async def main() -> None:
    """Start workers for all four task queues (Bulkhead, §6)."""
    from temporalio import client as temporal_client

    temporal_target = _get_temporal_target()
    namespace = _get_namespace()

    temporal_client = await temporal_client.Client.connect(
        temporal_target,
        namespace=namespace,
    )

    queues_and_activities = [
        (AGENT_QUEUE.name, [
            fetch_metrics,
            segment_data,
            detect_candidate_insights,
            rank_by_novelty,
            draft_narrative,
            validate_against_data,
            publish,
        ]),
        (NOTIFICATION_QUEUE.name, []),
        (CHAT_QUEUE.name, [
            segment_data,
        ]),
    ]

    workers = []
    for queue_name, activities in queues_and_activities:
        if activities:
            w = worker.Worker(
                client=temporal_client,
                workflows=[InsightGenerationWorkflow],
                activities=activities,
                task_queue=queue_name,
            )
            workers.append(w)

    # analysis-queue has no worker yet (synchronous API path, §9.2)
    # but the queue is reserved for future use

    await asyncio.gather(
        *[w.run() for w in workers],
    )


if __name__ == "__main__":
    asyncio.run(main())
