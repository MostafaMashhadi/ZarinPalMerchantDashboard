"""Dashboard summary and analysis endpoints (§11 API Contract).

GET  /api/v1/merchants/{merchant_ref}/dashboard/summary
POST /api/v1/merchants/{merchant_ref}/analysis/time-range
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


class DashboardSummaryController(APIView):
    """GET /api/v1/merchants/{merchant_ref}/dashboard/summary"""

    def get(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = self._resolve_merchant(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start_str = request.query_params.get("period_start")
        period_end_str = request.query_params.get("period_end")

        period_start = self._parse_datetime(period_start_str)
        period_end = self._parse_datetime(period_end_str)

        facade = AnalyticsFacade()
        result = facade.get_dashboard_summary(
            merchant_id=merchant_id,
            period_start=period_start,
            period_end=period_end,
        )
        return Response(result, status=status.HTTP_200_OK)

    @staticmethod
    def _resolve_merchant(merchant_ref: str) -> UUID | None:
        try:
            return UUID(merchant_ref)
        except ValueError:
            pass
        try:
            merchant = Merchant.objects.get(merchant_key__iexact=merchant_ref)
            return merchant.id
        except Merchant.DoesNotExist:
            return None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None


class AnalysisTimeRangeController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/analysis/time-range"""

    def post(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = self._resolve_merchant(merchant_ref)
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

        try:
            period_start = datetime.fromisoformat(period_start_str)
            period_end = datetime.fromisoformat(period_end_str)
        except (ValueError, TypeError):
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

        return Response(
            {
                "kind": result.kind,
                "merchant_id": str(result.merchant_id),
                "period_start": result.period_start.isoformat(),
                "period_end": result.period_end.isoformat(),
                "headline": result.headline,
                "body": result.body,
                "series": list(result.series),
                "provenance": [
                    {
                        "source_query_id": p.source_query_id,
                        "description": p.description,
                    }
                    for p in result.provenance
                ],
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _resolve_merchant(merchant_ref: str) -> UUID | None:
        try:
            return UUID(merchant_ref)
        except ValueError:
            pass
        try:
            merchant = Merchant.objects.get(merchant_key__iexact=merchant_ref)
            return merchant.id
        except Merchant.DoesNotExist:
            return None


__all__ = ["AnalysisTimeRangeController", "DashboardSummaryController"]
