"""
API-layer tests for the identity domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- All external deps (DB, Twilio, Temporal) mocked
- The IdentityService dependency overridden per test via app.dependency_overrides
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from elixir.domains.identity.schemas import (
    OTPRequestedResponse,
    RefreshResponse,
    VerifyOTPResponse,
)
from elixir.domains.identity.services import IdentityService, _OTPVerificationResult
from elixir.shared.exceptions import (
    OTPExpiredError,
    OTPInvalidError,
    OTPLockedError,
    RateLimitError,
    SessionExpiredError,
    SessionRevokedError,
)
from elixir.shared.security import create_access_token, create_refresh_token, hash_otp
from tests.conftest import PHONE, OTP_CODE, USER_ID, SESSION_ID, make_test_settings


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_app_with_service(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the identity service dependency
    with mock_service so we can test HTTP behaviour independently of service logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.identity.api import router as identity_router, get_identity_service
    from elixir.shared.exceptions import ElixirError
    from elixir.runtime.middleware import AuthMiddleware, RequestLoggingMiddleware
    from fastapi.exceptions import RequestValidationError

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock(return_value=None)
    mock_db.commit = AsyncMock(return_value=None)

    @asynccontextmanager
    async def _factory():
        yield mock_db

    app = FastAPI()
    app.state.settings = settings
    app.state.twilio = AsyncMock()
    app.state.temporal_client = AsyncMock()
    app.state.session_factory = _factory

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    app.include_router(identity_router, prefix="/auth")

    # Override the dependency so all routes use our mock service
    app.dependency_overrides[get_identity_service] = lambda: mock_service

    @app.exception_handler(ElixirError)
    async def elixir_handler(request: Request, exc: ElixirError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic v2 ctx.error is a live Exception — convert to str for JSON serialisation.
        def _serialisable(errors: list) -> list:
            safe = []
            for err in errors:
                entry = dict(err)
                if "ctx" in entry:
                    ctx = dict(entry["ctx"])
                    entry["ctx"] = {k: str(v) if isinstance(v, Exception) else v for k, v in ctx.items()}
                safe.append(entry)
            return safe

        return JSONResponse(
            status_code=422,
            content={"error": "VALIDATION_ERROR", "detail": _serialisable(exc.errors())},
        )

    return app


def _make_mock_service(**method_overrides):
    """Create an AsyncMock that behaves like IdentityService."""
    svc = AsyncMock(spec=IdentityService)
    for name, value in method_overrides.items():
        setattr(svc, name, value)
    return svc


# ── POST /auth/request-otp ────────────────────────────────────────────────────

class TestRequestOTPEndpoint:
    async def test_request_otp_returns_200(self):
        """Valid phone number → 200 with OTPRequestedResponse."""
        svc = _make_mock_service(
            request_otp=AsyncMock(return_value=OTPRequestedResponse(expires_in=60))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/request-otp", json={"phone": PHONE})

        assert resp.status_code == 200
        data = resp.json()
        assert data["expires_in"] == 60
        assert data["message"] == "OTP sent"

    async def test_request_otp_invalid_phone_returns_422(self):
        """Malformed phone number → 422 Validation Error."""
        svc = _make_mock_service()
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/request-otp", json={"phone": "not-a-phone"})

        assert resp.status_code == 422

    async def test_request_otp_rate_limited_returns_429(self):
        """Service raises RateLimitError → 429."""
        svc = _make_mock_service(
            request_otp=AsyncMock(side_effect=RateLimitError("Too many requests", phone=PHONE))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/request-otp", json={"phone": PHONE})

        assert resp.status_code == 429
        assert resp.json()["error"] == "RATE_LIMIT_EXCEEDED"

    async def test_request_otp_locked_returns_429(self):
        """Service raises OTPLockedError → 429."""
        svc = _make_mock_service(
            request_otp=AsyncMock(side_effect=OTPLockedError("Locked", locked_until="2099-01-01T00:00:00"))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/request-otp", json={"phone": PHONE})

        assert resp.status_code == 429
        assert resp.json()["error"] == "OTP_LOCKED"

    async def test_request_otp_normalises_phone_with_spaces(self):
        """Phone with spaces is normalised before service call."""
        svc = _make_mock_service(
            request_otp=AsyncMock(return_value=OTPRequestedResponse(expires_in=60))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/request-otp", json={"phone": "+91 9876 543210"})

        assert resp.status_code == 200
        # Service should be called with normalised E.164 (no spaces)
        svc.request_otp.assert_called_once_with("+919876543210")


# ── POST /auth/verify-otp ─────────────────────────────────────────────────────

class TestVerifyOTPEndpoint:
    async def test_verify_otp_returns_200_and_access_token(self):
        """Valid phone + OTP → 200, access_token in body, refresh_token in cookie."""
        settings = make_test_settings()
        access_token, _ = create_access_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.access_token_expiry_minutes
        )
        refresh_token, _ = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.refresh_token_expiry_days
        )
        svc = _make_mock_service(
            verify_otp=AsyncMock(return_value=_OTPVerificationResult(
                access_token=access_token,
                refresh_token=refresh_token,
            ))
        )
        app = _build_app_with_service(svc, settings=settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE, "otp": OTP_CODE})

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Refresh token must be in an httponly cookie
        assert "refresh_token" in resp.cookies

    async def test_verify_otp_wrong_code_returns_401(self):
        """Service raises OTPInvalidError → 401."""
        svc = _make_mock_service(
            verify_otp=AsyncMock(side_effect=OTPInvalidError("Invalid OTP."))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE, "otp": "000000"})

        assert resp.status_code == 401
        assert resp.json()["error"] == "OTP_INVALID"

    async def test_verify_otp_expired_returns_401(self):
        """Service raises OTPExpiredError → 401."""
        svc = _make_mock_service(
            verify_otp=AsyncMock(side_effect=OTPExpiredError("OTP has expired."))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE, "otp": OTP_CODE})

        assert resp.status_code == 401
        assert resp.json()["error"] == "OTP_EXPIRED"

    async def test_verify_otp_locked_returns_429(self):
        """Service raises OTPLockedError → 429."""
        svc = _make_mock_service(
            verify_otp=AsyncMock(side_effect=OTPLockedError("Locked", locked_until="2099-01-01T00:00:00"))
        )
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE, "otp": OTP_CODE})

        assert resp.status_code == 429

    async def test_verify_otp_invalid_otp_format_returns_422(self):
        """Non-numeric or wrong-length OTP → 422 Validation Error."""
        svc = _make_mock_service()
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 5-digit OTP (too short)
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE, "otp": "12345"})
        assert resp.status_code == 422

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # non-numeric
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE, "otp": "abcdef"})
        assert resp.status_code == 422

    async def test_verify_otp_missing_fields_returns_422(self):
        """Missing phone or otp field → 422."""
        svc = _make_mock_service()
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/verify-otp", json={"phone": PHONE})
        assert resp.status_code == 422


# ── POST /auth/refresh ────────────────────────────────────────────────────────

class TestRefreshEndpoint:
    async def test_refresh_returns_new_access_token(self):
        """Valid refresh_token cookie → 200 with new access_token."""
        settings = make_test_settings()
        new_access_token, _ = create_access_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.access_token_expiry_minutes
        )
        refresh_token, _ = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.refresh_token_expiry_days
        )
        svc = _make_mock_service(
            refresh_session=AsyncMock(return_value=RefreshResponse(access_token=new_access_token))
        )
        app = _build_app_with_service(svc, settings=settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_token)
            resp = await client.post("/auth/refresh")

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_without_cookie_returns_401(self):
        """No refresh_token cookie → 401."""
        svc = _make_mock_service()
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/refresh")  # no cookie

        assert resp.status_code == 401

    async def test_refresh_revoked_session_returns_401(self):
        """Service raises SessionRevokedError → 401."""
        settings = make_test_settings()
        refresh_token, _ = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.refresh_token_expiry_days
        )
        svc = _make_mock_service(
            refresh_session=AsyncMock(side_effect=SessionRevokedError("Session revoked."))
        )
        app = _build_app_with_service(svc, settings=settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_token)
            resp = await client.post("/auth/refresh")

        assert resp.status_code == 401
        assert resp.json()["error"] == "SESSION_REVOKED"

    async def test_refresh_expired_session_returns_401(self):
        """Service raises SessionExpiredError → 401."""
        settings = make_test_settings()
        refresh_token, _ = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.refresh_token_expiry_days
        )
        svc = _make_mock_service(
            refresh_session=AsyncMock(side_effect=SessionExpiredError("Session expired."))
        )
        app = _build_app_with_service(svc, settings=settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies.set("refresh_token", refresh_token)
            resp = await client.post("/auth/refresh")

        assert resp.status_code == 401
        assert resp.json()["error"] == "SESSION_EXPIRED"


# ── POST /auth/logout ─────────────────────────────────────────────────────────

class TestLogoutEndpoint:
    def _make_access_token(self, settings) -> str:
        token, _ = create_access_token(
            str(USER_ID), str(SESSION_ID),
            settings.jwt_secret, settings.access_token_expiry_minutes
        )
        return token

    async def test_logout_returns_204(self):
        """Authenticated logout → 204 No Content, refresh_token cookie cleared."""
        settings = make_test_settings()
        svc = _make_mock_service(logout=AsyncMock(return_value=None))
        app = _build_app_with_service(svc, settings=settings)
        access_token = self._make_access_token(settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert resp.status_code == 204

    async def test_logout_unauthenticated_returns_401(self):
        """No auth token → 401."""
        svc = _make_mock_service(logout=AsyncMock(return_value=None))
        app = _build_app_with_service(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/auth/logout")  # no auth header

        assert resp.status_code == 401

    async def test_logout_clears_refresh_cookie(self):
        """Successful logout → response deletes the refresh_token cookie."""
        settings = make_test_settings()
        svc = _make_mock_service(logout=AsyncMock(return_value=None))
        app = _build_app_with_service(svc, settings=settings)
        access_token = self._make_access_token(settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Set a refresh cookie first
            client.cookies.set("refresh_token", "some-token")
            resp = await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        # FastAPI's delete_cookie sets max_age=0; the Set-Cookie header should mention refresh_token
        set_cookie_header = resp.headers.get("set-cookie", "")
        assert "refresh_token" in set_cookie_header
