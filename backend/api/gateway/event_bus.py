"""InsightEventBus — Observer pattern event dispatcher (§6.4, §9.5).

Publish synchronously after the insight DB write commits.
Subscribers receive InsightPublishedEvent and act on it.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from shared.dtos import AnalysisResult


@dataclass(frozen=True, slots=True)
class InsightPublishedEvent:
    insight_id: uuid.UUID
    merchant_id: uuid.UUID
    kind: str
    period_start: datetime
    period_end: datetime
    headline: str


Subscriber = Callable[[InsightPublishedEvent], None]


class InsightEventBus:
    """Synchronous event bus — publishes after DB commit, never concurrently (§9.5).

    Subscribers are registered at startup. On Publish activity success,
    the InsightPublishedEvent is dispatched to all subscribers synchronously.
    """

    _instance: InsightEventBus | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []

    @classmethod
    def instance(cls) -> InsightEventBus:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        with cls._lock:
            cls._instance = None

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event: InsightPublishedEvent) -> None:
        """Dispatch to all subscribers synchronously (§9.5)."""
        for subscriber in list(self._subscribers):
            subscriber(event)

    def publish_from_result(self, result: AnalysisResult) -> InsightPublishedEvent:
        """Create and publish an InsightPublishedEvent from an AnalysisResult."""
        event = InsightPublishedEvent(
            insight_id=uuid.uuid4(),
            merchant_id=result.merchant_id,
            kind=result.kind,
            period_start=result.period_start,
            period_end=result.period_end,
            headline=result.headline,
        )
        self.publish(event)
        return event


__all__ = ["InsightEventBus", "InsightPublishedEvent", "Subscriber"]
