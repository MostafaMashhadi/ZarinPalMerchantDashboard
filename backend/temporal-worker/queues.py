"""Task queue names — Bulkhead isolation (§6, §9.2, §19.16).

Four separate Temporal task queues ensure that a backlog or crash in one
cannot block the others. chat-queue is defined now even though only
the scheduled ChatMemoryConsolidationWorkflow (Task 3.7) uses it yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskQueue:
    name: str


ANALYSIS_QUEUE = TaskQueue(name="analysis-queue")
AGENT_QUEUE = TaskQueue(name="agent-queue")
NOTIFICATION_QUEUE = TaskQueue(name="notification-queue")
CHAT_QUEUE = TaskQueue(name="chat-queue")

ALL_TASK_QUEUES: tuple[TaskQueue, ...] = (
    ANALYSIS_QUEUE,
    AGENT_QUEUE,
    NOTIFICATION_QUEUE,
    CHAT_QUEUE,
)


def get_queue(env_var: str, default: TaskQueue) -> TaskQueue:
    import os

    name = os.environ.get(env_var)
    if name:
        return TaskQueue(name=name)
    return default


__all__ = [
    "AGENT_QUEUE",
    "ALL_TASK_QUEUES",
    "ANALYSIS_QUEUE",
    "CHAT_QUEUE",
    "NOTIFICATION_QUEUE",
    "TaskQueue",
    "get_queue",
]
