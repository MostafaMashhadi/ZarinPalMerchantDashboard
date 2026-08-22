from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics"

    def ready(self) -> None:
        from gateway.event_bus import InsightEventBus
        from gateway.notification_service import NotificationService

        InsightEventBus.instance()
        NotificationService.instance().register()
