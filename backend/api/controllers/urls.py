from django.urls import path

from controllers.agent_controller import (
    AgentRunCostController,
    AgentRunPollController,
    AgentTriggerSummaryController,
)
from controllers.analytics_controller import (
    AnalysisAnomalyDetectionController,
    AnalysisCohortRetentionController,
    AnalysisEventImpactController,
    AnalysisPeerComparisonController,
    AnalysisTimeRangeController,
    DashboardSummaryController,
)
from controllers.auth_controller import LoginController, LogoutController, RefreshController
from controllers.chat_controller import (
    ChatSessionListController,
    ChatSessionMessagesController,
)
from controllers.health import HealthController
from controllers.notification_controller import (
    NotificationListController,
    NotificationMarkReadController,
)

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
    path(
        "merchants/<str:merchant_ref>/analysis/peer-comparison",
        AnalysisPeerComparisonController.as_view(),
        name="analysis-peer-comparison",
    ),
    path(
        "merchants/<str:merchant_ref>/analysis/event-impact",
        AnalysisEventImpactController.as_view(),
        name="analysis-event-impact",
    ),
    path(
        "merchants/<str:merchant_ref>/analysis/cohort-retention",
        AnalysisCohortRetentionController.as_view(),
        name="analysis-cohort-retention",
    ),
    path(
        "merchants/<str:merchant_ref>/analysis/anomaly-detection",
        AnalysisAnomalyDetectionController.as_view(),
        name="analysis-anomaly-detection",
    ),
    path(
        "merchants/<str:merchant_ref>/agent/trigger-summary",
        AgentTriggerSummaryController.as_view(),
        name="agent-trigger-summary",
    ),
    path(
        "merchants/<str:merchant_ref>/agent/runs/<str:run_id>",
        AgentRunPollController.as_view(),
        name="agent-run-poll",
    ),
    path(
        "merchants/<str:merchant_ref>/agent/runs/<str:run_id>/cost",
        AgentRunCostController.as_view(),
        name="agent-run-cost",
    ),
    path(
        "merchants/<str:merchant_ref>/notifications",
        NotificationListController.as_view(),
        name="notification-list",
    ),
    path(
        "merchants/<str:merchant_ref>/notifications/<str:notification_id>/mark-read",
        NotificationMarkReadController.as_view(),
        name="notification-mark-read",
    ),
    path("chat/sessions", ChatSessionListController.as_view(), name="chat-sessions"),
    path(
        "chat/sessions/<str:session_id>/messages",
        ChatSessionMessagesController.as_view(),
        name="chat-session-messages",
    ),
]
