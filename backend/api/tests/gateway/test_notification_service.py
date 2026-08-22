"""Tests for NotificationService subscriber and worker idempotency (§9.5, §19.10)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

_backend_dir = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")  # backend/
)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from gateway.event_bus import InsightEventBus, InsightPublishedEvent  # noqa: E402
from gateway.notification_service import NotificationService  # noqa: E402


def _env_side_effect(key: str, default: str = "") -> str:
    return "localhost" if key == "REDIS_HOST" else default


@pytest.fixture(autouse=True)
def reset_event_bus():
    InsightEventBus.reset_for_testing()
    NotificationService.reset_for_testing()
    yield
    InsightEventBus.reset_for_testing()
    NotificationService.reset_for_testing()


class TestNotificationServiceSubscriber:
    """NotificationService as a registered subscriber to InsightEventBus (§6.4, §9.5)."""

    def test_register_subscribes_to_bus(self):
        service = NotificationService()
        service.register()
        bus = InsightEventBus.instance()
        assert service.handle_event in bus._subscribers

    def test_handle_event_creates_notification(self):
        """Step 2: writes NOTIFICATION row with status='pending' (§9.5)."""
        event = InsightPublishedEvent(
            insight_id=uuid4(),
            merchant_id=uuid4(),
            kind="anomaly_detection",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Anomaly detected",
        )

        mock_merchant = MagicMock()
        mock_merchant.notification_prefs = {
            "severity_threshold": "info",
            "channels": ["in_app"],
        }

        with patch("merchants.models.Merchant.objects.get", return_value=mock_merchant):
            with patch("gateway.notification_service.transaction.atomic") as mock_atomic:
                mock_atomic.return_value.__enter__ = MagicMock(return_value=None)
                mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
                with patch("analytics.models.Notification.objects.create") as mock_create:
                    mock_create.return_value.id = uuid4()
                    service = NotificationService()
                    service.handle_event(event)

                    mock_create.assert_called_once()
                    call_kwargs = mock_create.call_args.kwargs
                    assert call_kwargs["status"] == "pending"
                    assert call_kwargs["channel"] == "in_app"

    def test_severity_below_threshold_skips_notification(self):
        """Step 1: per-merchant severity threshold filters events (§9.5)."""
        event = InsightPublishedEvent(
            insight_id=uuid4(),
            merchant_id=uuid4(),
            kind="anomaly_detection",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Info update",
        )

        mock_merchant = MagicMock()
        mock_merchant.notification_prefs = {
            "severity_threshold": "warning",
            "channels": ["in_app"],
        }

        with patch("merchants.models.Merchant.objects.get", return_value=mock_merchant):
            with patch("analytics.models.Notification.objects") as mock_objects:
                service = NotificationService()
                service.handle_event(event)
                mock_objects.create.assert_not_called()

    def test_critical_hits_warning_threshold(self):
        """Critical severity passes even warning threshold."""
        event = InsightPublishedEvent(
            insight_id=uuid4(),
            merchant_id=uuid4(),
            kind="anomaly_detection",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Critical anomaly detected",
        )

        mock_merchant = MagicMock()
        mock_merchant.notification_prefs = {
            "severity_threshold": "warning",
            "channels": ["in_app"],
        }

        with patch("merchants.models.Merchant.objects.get", return_value=mock_merchant):
            with patch("gateway.notification_service.transaction.atomic"):
                with patch("analytics.models.Notification.objects") as mock_objects:
                    service = NotificationService()
                    service.handle_event(event)
                    mock_objects.create.assert_called_once()

    def test_empty_channels_skips_notification(self):
        """If merchant has no channels configured, skip (§9.5)."""
        event = InsightPublishedEvent(
            insight_id=uuid4(),
            merchant_id=uuid4(),
            kind="anomaly_detection",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Anomaly detected",
        )

        mock_merchant = MagicMock()
        mock_merchant.notification_prefs = {
            "severity_threshold": "info",
            "channels": [],
        }

        with patch("merchants.models.Merchant.objects.get", return_value=mock_merchant):
            with patch("analytics.models.Notification.objects") as mock_objects:
                service = NotificationService()
                service.handle_event(event)
                mock_objects.create.assert_not_called()

    def test_uses_default_prefs_when_missing(self):
        """Missing prefs on merchant → uses default config (§9.5)."""
        mock_merchant = MagicMock()
        mock_merchant.notification_prefs = {}

        mock_objects = MagicMock()
        mock_objects.create.return_value = MagicMock(id=uuid4())
        with patch("merchants.models.Merchant.objects.get", return_value=mock_merchant):
            with patch("analytics.models.Notification.objects", mock_objects):
                with patch("gateway.notification_service.transaction.atomic"):
                    service = NotificationService()
                    prefs = service._extract_prefs(mock_merchant)
                    assert prefs.severity_threshold == "info"
                    assert prefs.channels == ["in_app"]


class TestNotificationServicePublishIntegration:
    """End-to-end: InsightEventBus.publish → NotificationService.handle_event."""

    def test_publish_to_bus_reaches_service(self):
        """The bus delivers events to all registered subscribers."""
        bus = InsightEventBus.instance()

        received = []
        bus.subscribe(received.append)

        event = InsightPublishedEvent(
            insight_id=uuid4(),
            merchant_id=uuid4(),
            kind="anomaly_detection",
            period_start=datetime.now(),
            period_end=datetime.now(),
            headline="Anomaly",
        )
        bus.publish(event)

        assert len(received) == 1
        assert received[0] == event


class TestNotificationWorkerIdempotency:
    """NOTIFICATION.id used as delivery idempotency key (§19.10).

    Tested against duplicate-send-on-retry.
    """

    def test_duplicate_notification_id_skipped(self):
        """If NOTIFICATION.id was already processed, skip (§19.10)."""
        from notification_worker.main import process_one_task

        mock_redis = MagicMock()
        mock_redis.brpop.return_value = (
            "notification-queue",
            json.dumps({
                "notification_id": "test-notif-id",
                "all_channels": ["in_app"],
            }),
        )
        mock_redis.exists.return_value = 1
        mock_redis.setex.return_value = True

        env_side_effect = _env_side_effect
        with patch("notification_worker.main.os.environ.get", side_effect=env_side_effect):
            with patch("redis.Redis", return_value=mock_redis):
                result = process_one_task()

        assert result is True

    def test_first_delivery_not_skipped(self):
        """First delivery attempt processes the notification."""
        from notification_worker.main import process_one_task

        mock_redis = MagicMock()
        mock_redis.brpop.return_value = (
            "notification-queue",
            json.dumps({
                "notification_id": "test-notif-2",
                "all_channels": ["in_app"],
            }),
        )
        mock_redis.exists.return_value = 0
        mock_redis.setex.return_value = True

        mock_notification = MagicMock()
        mock_notification.status = "pending"
        mock_notification.save = MagicMock()

        env_side_effect = _env_side_effect
        with patch("notification_worker.main.os.environ.get", side_effect=env_side_effect):
            with patch("redis.Redis", return_value=mock_redis):
                with patch(
                    "notification_worker.main.Notification.objects.get",
                    return_value=mock_notification,
                ):
                    result = process_one_task()

        assert result is True
        mock_notification.save.assert_called()

    def test_empty_queue_returns_false(self):
        """When queue is empty, worker returns False (no task processed)."""
        from notification_worker.main import process_one_task

        mock_redis = MagicMock()
        mock_redis.brpop.return_value = None

        env_side_effect = _env_side_effect
        with patch("notification_worker.main.os.environ.get", side_effect=env_side_effect):
            with patch("redis.Redis", return_value=mock_redis):
                result = process_one_task()

        assert result is False


class TestChannelAdapters:
    """Verify Adapter pattern for channels (§9.5, §19.10)."""

    def test_in_app_adapter_succeeds(self):
        from notification_worker.adapters.channels import (
            InAppNotificationAdapter,
        )

        notification = MagicMock()
        notification.payload = {
            "all_channels": ["in_app"],
            "headline": "Test",
        }

        adapter = InAppNotificationAdapter()
        result = adapter.deliver(notification)

        assert result.channel == "in_app"
        assert result.status == "sent"
        assert result.error is None

    def test_email_adapter_skipped_without_email_in_channels(self):
        from notification_worker.adapters.channels import EmailNotificationAdapter

        notification = MagicMock()
        notification.payload = {
            "all_channels": ["in_app"],
            "headline": "Test",
        }

        adapter = EmailNotificationAdapter()
        result = adapter.deliver(notification)

        assert result.channel == "email"
        assert result.status == "skipped"

    def test_email_adapter_no_smtp_config_fails(self):
        from notification_worker.adapters.channels import EmailNotificationAdapter

        notification = MagicMock()
        notification.payload = {
            "all_channels": ["email"],
            "headline": "Test",
            "recipient_email": "test@example.com",
        }

        adapter = EmailNotificationAdapter()
        with patch.dict("os.environ", {"SMTP_HOST": ""}):
            result = adapter.deliver(notification)

        assert result.channel == "email"
        assert result.status == "failed"

    def test_all_channels_use_adapter_pattern(self):
        """Verify in_app and email are the only adapters (SMS out of scope)."""
        from notification_worker.adapters.channels import CHANNEL_ADAPTERS

        assert "in_app" in CHANNEL_ADAPTERS
        assert "email" in CHANNEL_ADAPTERS
        assert "sms" not in CHANNEL_ADAPTERS
