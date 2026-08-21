"""Auth endpoint and service tests (§19.1-§19.3)."""

import uuid

import jwt
import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework.test import APIClient

from merchants.models import AuditLog, Category, Merchant, MerchantUser
from repositories.refresh_token_repository import RefreshTokenRepository
from services.auth_exceptions import InvalidRefreshTokenError
from services.auth_service import LOCKOUT_MAX_ATTEMPTS, AuthService
from services.jwt_service import TOKEN_TYPE_REFRESH


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def merchant_user(db):
    category = Category.objects.create(category_key="retail", title="Retail")
    merchant = Merchant.objects.create(
        merchant_key="M215",
        display_name="Test Merchant",
        category=category,
    )
    user = MerchantUser.objects.create(
        merchant=merchant,
        email="owner@example.com",
        password_hash=make_password("correct-password"),
        role="owner",
    )
    return user


@pytest.mark.django_db
def test_login_success(api_client, merchant_user):
    response = api_client.post(
        "/api/v1/auth/login",
        {"email": "owner@example.com", "password": "correct-password"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == settings.JWT_ACCESS_TTL_SECONDS
    assert body["access_token"]
    assert body["refresh_token"]

    access = jwt.decode(
        body["access_token"],
        settings.JWT_ACCESS_SECRET,
        algorithms=["HS256"],
    )
    assert access["sub"] == str(merchant_user.id)
    assert access["merchant_id"] == str(merchant_user.merchant_id)
    assert access["type"] == "access"

    merchant_user.refresh_from_db()
    assert merchant_user.failed_login_attempts == 0
    assert merchant_user.locked_until is None
    assert merchant_user.last_login_at is not None
    assert AuditLog.objects.filter(merchant_user=merchant_user, action="auth.login").exists()


@pytest.mark.django_db
def test_login_invalid_credentials_generic(api_client, merchant_user):
    response = api_client.post(
        "/api/v1/auth/login",
        {"email": "owner@example.com", "password": "wrong-password"},
        format="json",
    )

    assert response.status_code == 401
    assert response.json() == {"error": "INVALID_CREDENTIALS"}

    unknown = api_client.post(
        "/api/v1/auth/login",
        {"email": "nobody@example.com", "password": "wrong-password"},
        format="json",
    )
    assert unknown.status_code == 401
    assert unknown.json() == {"error": "INVALID_CREDENTIALS"}


@pytest.mark.django_db
def test_login_lockout_after_five_failures(api_client, merchant_user):
    for _ in range(LOCKOUT_MAX_ATTEMPTS):
        api_client.post(
            "/api/v1/auth/login",
            {"email": "owner@example.com", "password": "wrong-password"},
            format="json",
        )

    merchant_user.refresh_from_db()
    assert merchant_user.failed_login_attempts == LOCKOUT_MAX_ATTEMPTS
    assert merchant_user.locked_until is not None

    locked = api_client.post(
        "/api/v1/auth/login",
        {"email": "owner@example.com", "password": "correct-password"},
        format="json",
    )
    assert locked.status_code == 403
    assert locked.json()["error"] == "ACCOUNT_LOCKED"
    assert locked.json()["locked_until"]


@pytest.mark.django_db
def test_refresh_rotates_tokens(api_client, merchant_user):
    login = api_client.post(
        "/api/v1/auth/login",
        {"email": "owner@example.com", "password": "correct-password"},
        format="json",
    )
    old_refresh = login.json()["refresh_token"]

    refreshed = api_client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": old_refresh},
        format="json",
    )
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["refresh_token"] != old_refresh

    stale = api_client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": old_refresh},
        format="json",
    )
    assert stale.status_code == 401
    assert stale.json() == {"error": "INVALID_REFRESH_TOKEN"}


@pytest.mark.django_db
def test_logout_revokes_refresh_token(api_client, merchant_user):
    login = api_client.post(
        "/api/v1/auth/login",
        {"email": "owner@example.com", "password": "correct-password"},
        format="json",
    )
    refresh_token = login.json()["refresh_token"]

    logout = api_client.post(
        "/api/v1/auth/logout",
        {"refresh_token": refresh_token},
        format="json",
    )
    assert logout.status_code == 204

    refresh = api_client.post(
        "/api/v1/auth/refresh",
        {"refresh_token": refresh_token},
        format="json",
    )
    assert refresh.status_code == 401


@pytest.mark.django_db
def test_refresh_rejects_locked_account(api_client, merchant_user):
    merchant_user.failed_login_attempts = LOCKOUT_MAX_ATTEMPTS
    merchant_user.locked_until = timezone.now() + timezone.timedelta(minutes=15)
    merchant_user.save(update_fields=["failed_login_attempts", "locked_until"])

    refresh_token = jwt.encode(
        {
            "sub": str(merchant_user.id),
            "jti": str(uuid.uuid4()),
            "type": TOKEN_TYPE_REFRESH,
            "iat": timezone.now(),
            "exp": timezone.now() + timezone.timedelta(hours=1),
        },
        settings.JWT_REFRESH_SECRET,
        algorithm="HS256",
    )

    auth_service = AuthService(refresh_token_repository=RefreshTokenRepository())
    with pytest.raises(InvalidRefreshTokenError):
        auth_service.refresh(refresh_token=refresh_token)
