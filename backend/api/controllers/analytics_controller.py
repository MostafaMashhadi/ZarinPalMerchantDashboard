"""Dashboard summary and analysis endpoints (§11 API Contract).

GET  /api/v1/merchants/{merchant_ref}/dashboard/summary
POST /api/v1/merchants/{merchant_ref}/analysis/time-range
POST /api/v1/merchants/{merchant_ref}/analysis/peer-comparison
POST /api/v1/merchants/{merchant_ref}/analysis/event-impact
POST /api/v1/merchants/{merchant_ref}/analysis/cohort-retention
POST /api/v1/merchants/{merchant_ref}/analysis/anomaly-detection
"""

from datetime import datetime
from uuid import UUID

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.dtos import AnalysisParams

from facades.analytics_facade import AnalyticsFacade
from facades.authz import AuthPrincipal
from merchants.models import Merchant


def resolve_merchant_ref(merchant_ref: str) -> UUID | None:
    """Resolve merchant_ref (UUID or key) to internal UUID once at the edge."""
    try:
        return UUID(merchant_ref)
    except (ValueError, AttributeError):
        pass
    try:
        merchant = Merchant.objects.get(merchant_key__iexact=merchant_ref)
        return merchant.id
    except Merchant.DoesNotExist:
        return None


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _serialize_result(result) -> dict:
    return {
        "kind": result.kind,
        "merchant_id": str(result.merchant_id),
        "period_start": result.period_start.isoformat(),
        "period_end": result.period_end.isoformat(),
        "headline": result.headline,
        "body": result.body,
        "series": list(result.series),
        "low_confidence_peer_set": result.low_confidence_peer_set,
        "provenance": [
            {
                "source_query_id": p.source_query_id,
                "description": p.description,
            }
            for p in result.provenance
        ],
    }


def _get_principal(request: Request) -> AuthPrincipal | None:
    return getattr(request, "_auth_principal", None)


def _handle_period_params(request: Request) -> tuple[dict, datetime, datetime, str | None]:
    """Extract and validate period parameters.

    Returns (error_response, period_start, period_end, extra) tuple.
    If error_response is not None, the caller should return it immediately.
    """
    period_start_str = request.data.get("period_start") or request.query_params.get("period_start")
    period_end_str = request.data.get("period_end") or request.query_params.get("period_end")
    extra = request.data.get("extra", {}) or request.query_params.get("extra", {})

    if not period_start_str or not period_end_str:
        return (
            Response(
                {"error": "MISSING_PARAMETERS"},
                status=status.HTTP_400_BAD_REQUEST,
            ),
            None,
            None,
            extra,
        )

    period_start = parse_datetime(period_start_str)
    period_end = parse_datetime(period_end_str)
    if period_start is None or period_end is None:
        return (
            Response(
                {"error": "INVALID_PERIOD_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            ),
            None,
            None,
            extra,
        )

    if period_start >= period_end:
        return (
            Response(
                {"error": "PERIOD_START_MUST_PRECEDE_PERIOD_END"},
                status=status.HTTP_400_BAD_REQUEST,
            ),
            None,
            None,
            extra,
        )

    return None, period_start, period_end, extra


class _MerchantScopedController(APIView):
    """Base controller that handles 404/403 distinction per §19.23.

    - Unresolvable merchant_ref → 404
    - Resolvable but AuthZ fails → 403 (PermissionDenied from Facade)
    """

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied as exc:
            detail = exc.detail if hasattr(exc, "detail") else {}
            if isinstance(detail, dict):
                error_body = detail.get("error", "NOT_ENTITLED")
            else:
                error_body = "NOT_ENTITLED"
            return Response(
                {"error": error_body},
                status=status.HTTP_403_FORBIDDEN,
            )


class DashboardSummaryController(_MerchantScopedController):
    """GET /api/v1/merchants/{merchant_ref}/dashboard/summary"""

    def get(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start = parse_datetime(request.query_params.get("period_start"))
        period_end = parse_datetime(request.query_params.get("period_end"))
        principal = _get_principal(request)

        facade = AnalyticsFacade()
        result = facade.get_dashboard_summary(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
            principal=principal,
        )
        return Response(result, status=status.HTTP_200_OK)


class _AnalysisController(_MerchantScopedController):
    """Base for POST analysis controllers — shared period param handling."""

    analysis_kind: str = ""

    def _run_analysis(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        error, period_start, period_end, extra = _handle_period_params(request)
        if error is not None:
            return error

        params = AnalysisParams(
            period_start=period_start,
            period_end=period_end,
            extra=extra,
        )

        facade = AnalyticsFacade()
        result = facade.run_analysis(
            merchant_id=merchant_id,
            kind=self.analysis_kind,
            params=params,
            principal=_get_principal(request),
        )
        return Response(_serialize_result(result), status=status.HTTP_200_OK)


class AnalysisTimeRangeController(_AnalysisController):
    analysis_kind = "time_range"

    def post(self, request: Request, merchant_ref: str) -> Response:
        return self._run_analysis(request, merchant_ref)


class AnalysisPeerComparisonController(_AnalysisController):
    analysis_kind = "peer_comparison"

    def post(self, request: Request, merchant_ref: str) -> Response:
        return self._run_analysis(request, merchant_ref)


class AnalysisEventImpactController(_AnalysisController):
    analysis_kind = "event_impact"

    def post(self, request: Request, merchant_ref: str) -> Response:
        return self._run_analysis(request, merchant_ref)


class AnalysisCohortRetentionController(_AnalysisController):
    analysis_kind = "cohort_retention"

    def post(self, request: Request, merchant_ref: str) -> Response:
        return self._run_analysis(request, merchant_ref)


class AnalysisAnomalyDetectionController(_AnalysisController):
    analysis_kind = "anomaly_detection"

    def post(self, request: Request, merchant_ref: str) -> Response:
        return self._run_analysis(request, merchant_ref)


__all__ = [
    "AnalysisAnomalyDetectionController",
    "AnalysisCohortRetentionController",
    "AnalysisEventImpactController",
    "AnalysisPeerComparisonController",
    "AnalysisTimeRangeController",
    "DashboardSummaryController",
]
