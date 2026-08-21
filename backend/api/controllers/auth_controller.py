"""Auth endpoints: login, refresh, logout (§11)."""

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from facades.merchant_facade import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    MerchantFacade,
)


def _client_ip(request: Request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class LoginController(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        email = request.data.get("email")
        password = request.data.get("password")
        if not email or not password:
            return Response(
                {"error": "INVALID_CREDENTIALS"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        facade = MerchantFacade()
        try:
            result = facade.login(
                email=str(email).strip(),
                password=str(password),
                ip_address=_client_ip(request),
            )
        except AccountLockedError as exc:
            return Response(
                {
                    "error": "ACCOUNT_LOCKED",
                    "locked_until": exc.locked_until.isoformat(),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidCredentialsError:
            return Response(
                {"error": "INVALID_CREDENTIALS"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "expires_in": result.expires_in,
                "token_type": result.token_type,
            },
            status=status.HTTP_200_OK,
        )


class RefreshController(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response(
                {"error": "INVALID_REFRESH_TOKEN"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        facade = MerchantFacade()
        try:
            result = facade.refresh(refresh_token=str(refresh_token))
        except InvalidRefreshTokenError:
            return Response(
                {"error": "INVALID_REFRESH_TOKEN"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            {
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "expires_in": result.expires_in,
                "token_type": result.token_type,
            },
            status=status.HTTP_200_OK,
        )


class LogoutController(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request: Request) -> Response:
        refresh_token = request.data.get("refresh_token")
        if refresh_token:
            MerchantFacade().logout(refresh_token=str(refresh_token))
        return Response(status=status.HTTP_204_NO_CONTENT)
