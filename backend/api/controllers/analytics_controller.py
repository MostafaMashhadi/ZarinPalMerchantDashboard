"""Dashboard summary and analysis endpoints (§11 API Contract).

GET  /api/v1/merchants/{merchant_ref}/dashboard/summary
POST /api/v1/merchants/{merchant_ref}/analysis/time-range
POST /api/v1/merchants/{merchant_ref}/analysis/peer-comparison
"""

from datetime import datetime
from uuid import UUID

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.dtos import AnalysisParams

from facades.analytics_facade import AnalyticsFacade
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


class DashboardSummaryController(APIView):
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

        facade = AnalyticsFacade()
        result = facade.get_dashboard_summary(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )
        return Response(result, status=status.HTTP_200_OK)


class AnalysisTimeRangeController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/analysis/time-range"""

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start_str = request.data.get("period_start")
        period_end_str = request.data.get("period_end")
        extra = request.data.get("extra", {})

        if not period_start_str or not period_end_str:
            return Response(
                {"error": "MISSING_PARAMETERS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period_start = parse_datetime(period_start_str)
        period_end = parse_datetime(period_end_str)
        if period_start is None or period_end is None:
            return Response(
                {"error": "INVALID_PERIOD_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if period_start >= period_end:
            return Response(
                {"error": "PERIOD_START_MUST_PRECEDE_PERIOD_END"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = AnalysisParams(
            period_start=period_start,
            period_end=period_end,
            extra=extra,
        )

        facade = AnalyticsFacade()
        result = facade.run_analysis(
            merchant_id=merchant_id,
            kind="time_range",
            params=params,
        )
        return Response(_serialize_result(result), status=status.HTTP_200_OK)


class AnalysisPeerComparisonController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/analysis/peer-comparison (§19.9)."""

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start_str = request.data.get("period_start")
        period_end_str = request.data.get("period_end")
        extra = request.data.get("extra", {})

        if not period_start_str or not period_end_str:
            return Response(
                {"error": "MISSING_PARAMETERS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period_start = parse_datetime(period_start_str)
        period_end = parse_datetime(period_end_str)
        if period_start is None or period_end is None:
            return Response(
                {"error": "INVALID_PERIOD_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if period_start >= period_end:
            return Response(
                {"error": "PERIOD_START_MUST_PRECEDE_PERIOD_END"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = AnalysisParams(
            period_start=period_start,
            period_end=period_end,
            extra=extra,
        )

        facade = AnalyticsFacade()
        result = facade.run_analysis(
            merchant_id=merchant_id,
            kind="peer_comparison",
            params=params,
        )
        return Response(_serialize_result(result), status=status.HTTP_200_OK)


class AnalysisEventImpactController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/analysis/event-impact (§19.8)."""

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start_str = request.data.get("period_start")
        period_end_str = request.data.get("period_end")
        extra = request.data.get("extra", {})

        if not period_start_str or not period_end_str:
            return Response(
                {"error": "MISSING_PARAMETERS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period_start = parse_datetime(period_start_str)
        period_end = parse_datetime(period_end_str)
        if period_start is None or period_end is None:
            return Response(
                {"error": "INVALID_PERIOD_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if period_start >= period_end:
            return Response(
                {"error": "PERIOD_START_MUST_PRECEDE_PERIOD_END"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = AnalysisParams(
            period_start=period_start,
            period_end=period_end,
            extra=extra,
        )

        facade = AnalyticsFacade()
        result = facade.run_analysis(
            merchant_id=merchant_id,
            kind="event_impact",
            params=params,
        )
        return Response(_serialize_result(result), status=status.HTTP_200_OK)


class AnalysisCohortRetentionController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/analysis/cohort-retention (§19.10)."""

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start_str = request.data.get("period_start")
        period_end_str = request.data.get("period_end")
        extra = request.data.get("extra", {})

        if not period_start_str or not period_end_str:
            return Response(
                {"error": "MISSING_PARAMETERS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period_start = parse_datetime(period_start_str)
        period_end = parse_datetime(period_end_str)
        if period_start is None or period_end is None:
            return Response(
                {"error": "INVALID_PERIOD_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if period_start >= period_end:
            return Response(
                {"error": "PERIOD_START_MUST_PRECEDE_PERIOD_END"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = AnalysisParams(
            period_start=period_start,
            period_end=period_end,
            extra=extra,
        )

        facade = AnalyticsFacade()
        result = facade.run_analysis(
            merchant_id=merchant_id,
            kind="cohort_retention",
            params=params,
        )
        return Response(_serialize_result(result), status=status.HTTP_200_OK)


class AnalysisAnomalyDetectionController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/analysis/anomaly-detection (§19.11)."""

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start_str = request.data.get("period_start")
        period_end_str = request.data.get("period_end")
        extra = request.data.get("extra", {})

        if not period_start_str or not period_end_str:
            return Response(
                {"error": "MISSING_PARAMETERS"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period_start = parse_datetime(period_start_str)
        period_end = parse_datetime(period_end_str)
        if period_start is None or period_end is None:
            return Response(
                {"error": "INVALID_PERIOD_FORMAT"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if period_start >= period_end:
            return Response(
                {"error": "PERIOD_START_MUST_PRECEDE_PERIOD_END"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params = AnalysisParams(
            period_start=period_start,
            period_end=period_end,
            extra=extra,
        )

        facade = AnalyticsFacade()
        result = facade.run_analysis(
            merchant_id=merchant_id,
            kind="anomaly_detection",
            params=params,
        )
        return Response(_serialize_result(result), status=status.HTTP_200_OK)


__all__ = [
    "AnalysisAnomalyDetectionController",
    "AnalysisCohortRetentionController",
    "AnalysisEventImpactController",
    "AnalysisPeerComparisonController",
    "AnalysisTimeRangeController",
    "DashboardSummaryController",
]
