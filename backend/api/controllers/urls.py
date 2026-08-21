from django.urls import path

from controllers.auth_controller import LoginController, LogoutController, RefreshController
from controllers.health import HealthController

urlpatterns = [
    path("health", HealthController.as_view(), name="health"),
    path("auth/login", LoginController.as_view(), name="auth-login"),
    path("auth/refresh", RefreshController.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutController.as_view(), name="auth-logout"),
]
