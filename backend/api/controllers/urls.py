from django.urls import path

from controllers.health import HealthController

urlpatterns = [
    path("health", HealthController.as_view(), name="health"),
]
