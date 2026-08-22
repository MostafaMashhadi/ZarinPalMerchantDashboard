"""Agent API endpoints (§11, §19.6, §19.7).

POST /api/v1/merchants/{merchant_ref}/agent/trigger-summary
  - Idempotency-Key header required
  - Triggers InsightGenerationWorkflow on agent-queue
  - Returns run_id immediately

GET  /api/v1/merchants/{merchant_ref}/agent/runs/{run_id}
  - Polls workflow status

GET  /api/v1/merchants/{merchant_ref}/agent/runs/{run_id}/cost
  - Returns cost info for the run
"""

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from facades.authz import AuthPrincipal
from merchants.models import Merchant
from services.agent_orchestration_service import AgentOrchestrationService


def _resolve_merchant_ref(merchant_ref: str) -> UUID | None:
    try:
        return UUID(merchant_ref)
    except (ValueError, AttributeError):
        pass
    try:
        merchant = Merchant.objects.get(merchant_key__iexact=merchant_ref)
        return merchant.id
    except Merchant.DoesNotExist:
        return None


class AgentTriggerSummaryController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/agent/trigger-summary

    Requires Idempotency-Key header (§10.2).
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service: AgentOrchestrationService | None = None

    def _get_service(self) -> AgentOrchestrationService:
        if self._service is None:
            self._service = AgentOrchestrationService()
        return self._service

    def _resolve_merchant(self, merchant_ref: str) -> UUID | None:
        return _resolve_merchant_ref(merchant_ref)

    def _get_principal(self, request: Request) -> AuthPrincipal | None:
        return getattr(request, "auth_principal", None)

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = self._resolve_merchant(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        principal = self._get_principal(request)

        kind = request.data.get("kind", "time_range")
        from datetime import datetime as dt

        period_start = request.data.get("period_start")
        period_end = request.data.get("period_end")
        if period_start:
            period_start = dt.fromisoformat(period_start)
        else:
            from datetime import timedelta

            period_start = dt.now() - timedelta(days=30)
        if period_end:
            period_end = dt.fromisoformat(period_end)
        else:
            period_end = dt.now()

        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY")
        if not idempotency_key:
            return Response(
                {"error": "IDEMPOTENCY_KEY_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingest_batch_id = request.data.get("ingest_batch_id")
        if ingest_batch_id:
            ingest_batch_id = UUID(ingest_batch_id)

        result = self._get_service().trigger_summary(
            merchant_id=merchant_id,
            kind=kind,
            period_start=period_start,
            period_end=period_end,
            idempotency_key=idempotency_key,
            principal=principal,
            ingest_batch_id=ingest_batch_id,
        )

        status_code = (
            status.HTTP_200_OK
            if result.get("status") == "running"
            else status.HTTP_202_ACCEPTED
        )
        return Response(result, status=status_code)


class AgentRunPollController(APIView):
    """GET /api/v1/merchants/{merchant_ref}/agent/runs/{run_id}"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service: AgentOrchestrationService | None = None

    def _get_service(self) -> AgentOrchestrationService:
        if self._service is None:
            self._service = AgentOrchestrationService()
        return self._service

    def get(self, request: Request, merchant_ref: str, run_id: str) -> Response:
        merchant_id = _resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = self._get_service().poll_run(merchant_id, run_id)
        return Response(result)


class AgentRunCostController(APIView):
    """GET /api/v1/merchants/{merchant_ref}/agent/runs/{run_id}/cost"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._service: AgentOrchestrationService | None = None

    def _get_service(self) -> AgentOrchestrationService:
        if self._service is None:
            self._service = AgentOrchestrationService()
        return self._service

    def get(self, request: Request, merchant_ref: str, run_id: str) -> Response:
        merchant_id = _resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = self._get_service().get_run_cost(merchant_id, run_id)
        return Response(result)


__all__ = [
    "AgentRunCostController",
    "AgentRunPollController",
    "AgentTriggerSummaryController",
]
