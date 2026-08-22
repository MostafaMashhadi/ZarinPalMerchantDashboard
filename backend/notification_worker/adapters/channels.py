"""Notification channel adapters — Adapter pattern (§9.5, §19.10).

In-app + email only. SMS is out of scope. Each adapter is stateless
and can be swapped for a different backend without touching the
delivery worker logic.
"""

from __future__ import annotations

import os
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.text import MIMEText

from analytics.models import Notification


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Result of a single channel delivery attempt."""

    notification_id: str
    channel: str
    status: str
    error: str | None = None


class NotificationChannelAdapter(ABC):
    """Base adapter interface — each channel implements this (§19.10)."""

    @abstractmethod
    def deliver(self, notification: Notification) -> DeliveryResult:
        """Attempt to deliver a notification via this channel."""
        ...


class InAppNotificationAdapter(NotificationChannelAdapter):
    """Delivers notifications to the in-app notification bell (§9.5)."""

    def deliver(self, notification: Notification) -> DeliveryResult:
        try:
            payload = notification.payload
            channels = payload.get("channels", ["in_app"])
            if "in_app" in channels:
                return DeliveryResult(
                    notification_id=str(notification.id),
                    channel="in_app",
                    status="sent",
                )
            return DeliveryResult(
                notification_id=str(notification.id),
                channel="in_app",
                status="skipped",
            )
        except Exception as exc:
            return DeliveryResult(
                notification_id=str(notification.id),
                channel="in_app",
                status="failed",
                error=str(exc),
            )


class EmailNotificationAdapter(NotificationChannelAdapter):
    """Delivers notifications via email (§9.5, §19.10)."""

    def deliver(self, notification: Notification) -> DeliveryResult:
        try:
            payload = notification.payload
            merchant_user_email = payload.get("recipient_email")
            if not merchant_user_email:
                return DeliveryResult(
                    notification_id=str(notification.id),
                    channel="email",
                    status="skipped",
                )

            smtp_host = os.environ.get("SMTP_HOST", "")
            if not smtp_host:
                return DeliveryResult(
                    notification_id=str(notification.id),
                    channel="email",
                    status="failed",
                    error="SMTP not configured",
                )

            msg = MIMEText(payload.get("headline", "No subject"))
            msg["Subject"] = payload.get("headline", "Notification")
            msg["From"] = os.environ.get("SMTP_FROM", "noreply@example.com")
            msg["To"] = merchant_user_email

            smtp_port = int(os.environ.get("SMTP_PORT", "587"))
            smtp_user = os.environ.get("SMTP_USER", "")
            smtp_pass = os.environ.get("SMTP_PASSWORD", "")

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return DeliveryResult(
                notification_id=str(notification.id),
                channel="email",
                status="sent",
            )
        except Exception as exc:
            return DeliveryResult(
                notification_id=str(notification.id),
                channel="email",
                status="failed",
                error=str(exc),
            )


CHANNEL_ADAPTERS: dict[str, NotificationChannelAdapter] = {
    "in_app": InAppNotificationAdapter(),
    "email": EmailNotificationAdapter(),
}


def get_adapter(channel: str) -> NotificationChannelAdapter | None:
    return CHANNEL_ADAPTERS.get(channel)


__all__ = [
    "CHANNEL_ADAPTERS",
    "DeliveryResult",
    "EmailNotificationAdapter",
    "InAppNotificationAdapter",
    "NotificationChannelAdapter",
    "get_adapter",
]
