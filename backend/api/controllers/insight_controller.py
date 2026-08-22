"""Insights list and detail endpoints (§11 API Contract, §19.21).

GET /api/v1/merchants/{merchant_ref}/insights
  - Lists insights for the merchant with pagination
  - Pagination defaults: limit=20, offset=0
"""

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from facades.analytics_facade import AnalyticsFacade
from facades.authz import AuthPrincipal
from merchants.models import Merchant


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


def _get_principal(request: Request) -> AuthPrincipal | None:
    return getattr(request, "_auth_principal", None)


class InsightListController(APIView):
    """GET /api/v1/merchants/{merchant_ref}/insights (§19.21)."""

    def get(self, request: Request, merchant_ref: str) -> Response:
        merchant_id = _resolve_merchant_ref(merchant_ref)
        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        kind = request.query_params.get("kind")
        try:
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))
        except ValueError:
            limit, offset = 20, 0

        if limit > 100:
            limit = 100

        facade = AnalyticsFacade()
        insights = facade.list_insights(
            merchant_id=merchant_id,
            kind=kind,
            limit=limit,
            offset=offset,
            principal=_get_principal(request),
        )

        return Response(
            {"insights": insights, "count": len(insights)},
            status=status.HTTP_200_OK,
        )


__all__ = ["InsightListController"]
