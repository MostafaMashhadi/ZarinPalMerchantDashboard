"""NotificationService — registered subscriber to InsightEventBus (§6.4, §9.5).

Implements the 5-step notification flow:
1. Applies per-merchant notification preferences (channel, severity threshold).
2. Writes a NOTIFICATION row with status = 'pending'.
3. Enqueues delivery onto the notification-queue (Bulkhead-isolated).
4. A separate delivery worker marks status = 'sent' or 'failed' after
   attempting the channel send (in-app + email only; SMS out of scope).

NOTIFICATION.id is used as the delivery idempotency key.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from analytics.models import Notification
from gateway.event_bus import InsightEventBus, InsightPublishedEvent

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}

SEVERITY_THRESHOLD = "info"
CHANNELS = ["in_app"]


@dataclass(frozen=True, slots=True)
class MerchantNotificationPrefs:
    severity_threshold: str = SEVERITY_THRESHOLD
    channels: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.channels is None:
            object.__setattr__(self, "channels", list(CHANNELS))


class NotificationService:
    """Subscriber to InsightEventBus — implements §9.5's 5-step flow.

    Registered at startup via `register(app)`.

    The Orchestrator/Strategy layer only calls `publish()` — it has zero
    knowledge of who is listening (§6.4).
    """

    _instance: NotificationService | None = None

    def __init__(self, *, notification_repo=None) -> None:
        self._repo = notification_repo

    @classmethod
    def instance(cls) -> NotificationService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_testing(cls) -> None:
        cls._instance = None

    def register(self) -> None:
        """Register as a subscriber on the InsightEventBus (§6.4)."""
        bus = InsightEventBus.instance()
        bus.subscribe(self.handle_event)

    def handle_event(self, event: InsightPublishedEvent) -> None:
        """Entry point as an InsightEventBus subscriber (§9.5).

        Implements the 5-step flow:
        1. Apply per-merchant preferences (channel, severity threshold).
        2. Write NOTIFICATION row with status='pending'.
        3. Enqueue delivery onto notification-queue.
        4. Delivery worker picks it up and marks sent/failed.
        """
        try:
            from merchants.models import Merchant

            merchant = Merchant.objects.get(pk=event.merchant_id)
            prefs = self._extract_prefs(merchant)

            if not self._severity_passes(prefs.severity_threshold, event):
                return

            if not prefs.channels:
                return

            with transaction.atomic():
                notification = Notification.objects.create(
                    merchant=merchant,
                    insight_id=event.insight_id,
                    channel=prefs.channels[0] if prefs.channels else "in_app",
                    status="pending",
                    payload={
                        "kind": event.kind,
                        "headline": event.headline,
                        "period_start": event.period_start.isoformat(),
                        "period_end": event.period_end.isoformat(),
                        "all_channels": prefs.channels,
                    },
                    created_at=timezone.now(),
                )

            self._enqueue_delivery(notification.id, prefs.channels)
        except Exception:
            pass

    def _extract_prefs(self, merchant: Any) -> MerchantNotificationPrefs:
        """Read notification preferences from MERCHANT settings (§9.5)."""
        prefs = getattr(merchant, "notification_prefs", None) or {}
        severity = prefs.get(
            "severity_threshold",
            getattr(settings, "NOTIFICATION_DEFAULT_SEVERITY_THRESHOLD", "info"),
        )
        channels = prefs.get(
            "channels",
            getattr(settings, "NOTIFICATION_CHANNELS_DEFAULT", "in_app"),
        )
        if isinstance(channels, str):
            channels = [channels]
        return MerchantNotificationPrefs(
            severity_threshold=severity,
            channels=channels,
        )

    @staticmethod
    def _severity_passes(threshold: str, event: InsightPublishedEvent) -> bool:
        """Apply severity threshold from §9.5 step 1."""
        severity = event.headline.lower()
        threshold_rank = SEVERITY_ORDER.get(threshold, 0)
        if "anomal" in severity or "critical" in severity:
            event_severity_rank = SEVERITY_ORDER.get("critical", 2)
        elif "warning" in severity or "alert" in severity:
            event_severity_rank = SEVERITY_ORDER.get("warning", 1)
        else:
            event_severity_rank = SEVERITY_ORDER.get("info", 0)
        return event_severity_rank >= threshold_rank

    @staticmethod
    def _enqueue_delivery(notification_id: str, channels: list[str]) -> None:
        """Enqueue delivery onto notification-queue (§9.5 step 3).

        Uses Redis list push as a simple durable queue. A dedicated
        delivery worker (notification-worker/) pops and delivers.
        NOTIFICATION.id is the idempotency key.
        """
        redis_host = os.environ.get("REDIS_HOST", "")
        if not redis_host:
            return
        try:
            import redis

            client = redis.Redis(
                host=redis_host,
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD") or None,
                decode_responses=True,
            )
            payload = json.dumps(
                {"notification_id": notification_id, "channels": channels}
            )
            client.lpush("notification-queue", payload)
        except Exception:
            pass


__all__ = ["MerchantNotificationPrefs", "NotificationService"]
