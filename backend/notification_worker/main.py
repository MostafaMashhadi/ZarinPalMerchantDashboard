"""Notification delivery worker — runs on notification-queue (§9.5, §19.10).

Pops delivery tasks from Redis list 'notification-queue' and dispatches
to the appropriate channel adapter. NOTIFICATION.id is used as the
idempotency key — duplicate delivery attempts for the same notification
are deduplicated.
"""

from __future__ import annotations

import json
import logging
import os
import time

from django.utils import timezone

from analytics.models import Notification
from notification_worker.adapters.channels import get_adapter

logger = logging.getLogger(__name__)

DELIVERY_RETRY_KEY_PREFIX = "notification:delivered:"


def process_one_task() -> bool:
    """Pop and process one notification delivery task from the queue.

    Returns True if a task was processed, False if queue was empty.
    """
    redis_host = os.environ.get("REDIS_HOST", "")
    if not redis_host:
        return False

    try:
        import redis

        client = redis.Redis(
            host=redis_host,
            port=int(os.environ.get("REDIS_PORT", "6379")),
            password=os.environ.get("REDIS_PASSWORD") or None,
            decode_responses=True,
        )
        raw = client.brpop("notification-queue", timeout=1)
        if raw is None:
            return False

        _, payload_str = raw
        payload = json.loads(payload_str)
        notification_id = payload["notification_id"]
        channels = payload.get("all_channels", ["in_app"])

        idempotency_key = f"{DELIVERY_RETRY_KEY_PREFIX}{notification_id}"

        if client.exists(idempotency_key):
            logger.info(
                "Duplicate delivery attempt for notification %s, skipping",
                notification_id,
            )
            return True

        try:
            notification = Notification.objects.get(pk=notification_id)
        except Notification.DoesNotExist:
            logger.warning("Notification %s not found", notification_id)
            client.setex(idempotency_key, 86400, "1")
            return True

        all_sent = True
        for channel in channels:
            adapter = get_adapter(channel)
            if adapter is None:
                logger.warning("Unknown channel %s", channel)
                continue
            result = adapter.deliver(notification)
            if result.status != "sent":
                all_sent = False
                logger.error(
                    "Delivery failed for notification %s on channel %s: %s",
                    notification_id,
                    channel,
                    result.error,
                )

        if all_sent:
            notification.status = "sent"
            notification.sent_at = timezone.now()
        else:
            notification.status = "failed"
        notification.save(update_fields=["status", "sent_at"])

        client.setex(idempotency_key, 86400, "1")
        return True
    except Exception as exc:
        logger.error("Delivery worker error: %s", exc)
        return False


def main() -> None:
    """Run the notification delivery worker loop."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

    import django

    django.setup()

    logger.info("Notification worker starting on notification-queue")
    while True:
        try:
            processed = process_one_task()
            if not processed:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Notification worker shutting down")
            break
        except Exception as exc:
            logger.error("Unexpected error: %s", exc)
            time.sleep(5)


if __name__ == "__main__":
    main()
