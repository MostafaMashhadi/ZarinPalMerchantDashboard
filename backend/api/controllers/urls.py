from django.urls import path

from controllers.analytics_controller import (
    AnalysisTimeRangeController,
    DashboardSummaryController,
)
from controllers.auth_controller import LoginController, LogoutController, RefreshController
from controllers.health import HealthController

urlpatterns = [
    path("health", HealthController.as_view(), name="health"),
    path("auth/login", LoginController.as_view(), name="auth-login"),
    path("auth/refresh", RefreshController.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutController.as_view(), name="auth-logout"),
    path(
        "merchants/<str:merchant_ref>/dashboard/summary",
        DashboardSummaryController.as_view(),
        name="dashboard-summary",
    ),
    path(
        "merchants/<str:merchant_ref>/analysis/time-range",
        AnalysisTimeRangeController.as_view(),
        name="analysis-time-range",
    ),
]
