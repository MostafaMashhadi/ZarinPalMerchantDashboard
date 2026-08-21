"""JWT authentication middleware — extracts principal from access token (§13).

Sits at the edge layer, after rate limiting but before the Controller.
Attaches the resolved AuthPrincipal to request._auth_principal
so that the rate limiter can use it for identity and Facades can
enforce object-level AuthZ.

Auth endpoints (login/refresh/logout) are excluded — they authenticate
themselves via the Facade.
"""

from __future__ import annotations

from collections.abc import Callable

import jwt
from django.http import JsonResponse

from facades.authz import AuthPrincipal
from services.jwt_service import JwtService

_UNAUTHENTICATED_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/health",
})


class JwtAuthenticationMiddleware:
    """Extracts and validates the JWT access token, attaching principal to request.

    Runs before the view. On invalid/expired token, returns 401.
    On valid token, sets request._auth_principal = AuthPrincipal.
    Auth endpoints bypass this middleware entirely.
    """

    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response
        self._jwt_service: JwtService | None = None

    def __call__(self, request):
        path = request.path_info
        if path in _UNAUTHENTICATED_PATHS:
            return self.get_response(request)

        token = self._extract_token(request)
        if token is None:
            request._auth_principal = None
            return self.get_response(request)

        try:
            claims = self._get_jwt_service().decode_access_token(token)
            request._auth_principal = AuthPrincipal(
                user_id=claims.user_id,
                merchant_id=claims.merchant_id,
                role=claims.role,
                email=claims.email,
            )
        except jwt.InvalidTokenError:
            return JsonResponse(
                {"error": "INVALID_TOKEN"},
                status=401,
            )

        return self.get_response(request)

    def _extract_token(self, request) -> str | None:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    def _get_jwt_service(self) -> JwtService:
        if self._jwt_service is None:
            self._jwt_service = JwtService()
        return self._jwt_service


__all__ = ["JwtAuthenticationMiddleware"]
