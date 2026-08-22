"""Notification API endpoints (§11, §19.9).

GET  /api/v1/merchants/{merchant_ref}/notifications?status=&page=
POST /api/v1/merchants/{merchant_ref}/notifications/{notification_id}/mark-read
"""

from __future__ import annotations

from uuid import UUID

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.models import Notification
from merchants.models import Merchant

PAGE_SIZE = 20


class NotificationListController(APIView):
    """GET /api/v1/merchants/{merchant_ref}/notifications?status=&page="""

    def get(self, request: Request, merchant_ref: str) -> Response:
        principal = getattr(request, "auth_principal", None)

        merchant_id: UUID | None = None
        try:
            merchant_id = UUID(merchant_ref)
        except (ValueError, AttributeError):
            try:
                merchant = Merchant.objects.get(
                    merchant_key__iexact=merchant_ref
                )
                merchant_id = merchant.id
                if principal:
                    from facades.authz import AuthzEnforcer

                    AuthzEnforcer().check_object_permission(principal, merchant_id)
            except Merchant.DoesNotExist:
                return Response(
                    {"error": "MERCHANT_NOT_FOUND"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        status_filter = request.query_params.get("status", "")
        page = int(request.query_params.get("page", "1"))
        if page < 1:
            page = 1

        notifications = Notification.objects.filter(merchant_id=merchant_id)
        if status_filter:
            notifications = notifications.filter(status=status_filter)

        notifications = notifications.order_by("-created_at")
        total = notifications.count()
        start = (page - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = notifications[start:end]

        return Response({
            "notifications": [
                {
                    "id": str(n.id),
                    "status": n.status,
                    "channel": n.channel,
                    "payload": n.payload,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                    "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                }
                for n in page_items
            ],
            "page": page,
            "page_size": PAGE_SIZE,
            "total": total,
            "has_next": (start + PAGE_SIZE) < total,
        })


class NotificationMarkReadController(APIView):
    """POST /api/v1/merchants/{merchant_ref}/notifications/{notification_id}/mark-read"""

    def post(
        self,
        request: Request,
        merchant_ref: str,
        notification_id: str,
    ) -> Response:
        merchant_id: UUID | None = None
        try:
            merchant_id = UUID(merchant_ref)
        except (ValueError, AttributeError):
            try:
                merchant = Merchant.objects.get(
                    merchant_key__iexact=merchant_ref
                )
                merchant_id = merchant.id
            except Merchant.DoesNotExist:
                return Response(
                    {"error": "MERCHANT_NOT_FOUND"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if merchant_id is None:
            return Response(
                {"error": "MERCHANT_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            notification = Notification.objects.get(
                pk=notification_id,
                merchant_id=merchant_id,
            )
        except Notification.DoesNotExist:
            return Response(
                {"error": "NOTIFICATION_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification.status = "read"
        notification.save(update_fields=["status"])

        return Response({
            "id": str(notification.id),
            "status": notification.status,
        })


__all__ = ["NotificationListController", "NotificationMarkReadController"]
