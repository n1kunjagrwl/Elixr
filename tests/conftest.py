"""
Root conftest.py — shared pytest fixtures for the Elixir test suite.

Strategy:
- Service tests: use AsyncMock / MagicMock to fully mock the AsyncSession
  and repository methods. No real DB required.
- API tests: build a real FastAPI app with a mocked session_factory,
  mocked Twilio, and mocked Temporal client. Uses httpx.AsyncClient.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from elixir.shared.config import Settings
from elixir.shared.security import create_access_token, create_refresh_token, hash_otp


# ── Test Settings ─────────────────────────────────────────────────────────────

def make_test_settings(**overrides) -> Settings:
    """Return a Settings instance with safe, fast test values."""
    base = dict(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret="test-secret-key-that-is-long-enough-32c",
        encryption_key="0" * 64,  # 32 bytes hex encoded
        otp_expiry_seconds=60,
        otp_max_attempts=3,
        otp_lockout_minutes=5,
        otp_rate_limit_count=5,
        otp_rate_limit_window_minutes=15,
        access_token_expiry_minutes=15,
        refresh_token_expiry_days=7,
        twilio_account_sid="test_sid",
        twilio_auth_token="test_auth",
        twilio_verify_service_sid="test_vsid",
        temporal_address="localhost:7233",
        temporal_task_queue="test-queue",
        outbox_poll_interval_seconds=9999,  # effectively disable in tests
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def test_settings() -> Settings:
    return make_test_settings()


# ── Mock External Clients ──────────────────────────────────────────────────────

@pytest.fixture
def mock_twilio() -> AsyncMock:
    """Mock Twilio client — records calls, never sends SMS."""
    client = AsyncMock()
    client.send_otp = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_temporal() -> AsyncMock:
    """Mock Temporal client — start_workflow returns immediately."""
    client = AsyncMock()
    client.start_workflow = AsyncMock(return_value=None)
    return client


# ── Mock DB Session ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_db() -> AsyncMock:
    """
    Lightweight AsyncMock of an SQLAlchemy AsyncSession.
    flush() and commit() are no-ops. add() captures the added object.
    """
    db = AsyncMock()
    db.flush = AsyncMock(return_value=None)
    db.commit = AsyncMock(return_value=None)
    db.rollback = AsyncMock(return_value=None)
    db.add = MagicMock(return_value=None)
    return db


# ── Common Test Data ──────────────────────────────────────────────────────────

PHONE = "+919876543210"
OTP_CODE = "123456"
USER_ID = uuid.uuid4()
SESSION_ID = uuid.uuid4()


@pytest.fixture
def sample_user():
    """A mock User ORM object."""
    user = MagicMock()
    user.id = USER_ID
    user.phone_e164 = PHONE
    user.is_active = True
    return user


@pytest.fixture
def sample_otp_request(sample_user):
    """An active, unhashed OTP request for the sample user."""
    now = datetime.now(timezone.utc)
    otp_req = MagicMock()
    otp_req.id = uuid.uuid4()
    otp_req.user_id = sample_user.id
    otp_req.code_hash = hash_otp(OTP_CODE)
    otp_req.expires_at = now + timedelta(seconds=60)
    otp_req.attempt_count = 0
    otp_req.locked_until = None
    otp_req.used_at = None
    return otp_req


@pytest.fixture
def sample_session(sample_user, test_settings):
    """A mock Session ORM object with valid JTIs."""
    now = datetime.now(timezone.utc)
    _, access_jti = create_access_token(
        str(sample_user.id), str(SESSION_ID),
        test_settings.jwt_secret,
        test_settings.access_token_expiry_minutes,
    )
    refresh_token, refresh_jti = create_refresh_token(
        str(sample_user.id), str(SESSION_ID),
        test_settings.jwt_secret,
        test_settings.refresh_token_expiry_days,
    )
    session = MagicMock()
    session.id = SESSION_ID
    session.user_id = sample_user.id
    session.access_token_jti = access_jti
    session.refresh_token_jti = refresh_jti
    session.expires_at = now + timedelta(days=7)
    session.revoked_at = None
    # Store generated refresh_token for use in tests
    session._refresh_token = refresh_token
    return session


# ── FastAPI Test App ──────────────────────────────────────────────────────────

def _make_mock_session_factory(mock_db: AsyncMock):
    """
    Build a callable that, when used as `async with factory() as session`,
    yields mock_db. This satisfies get_db_session's `async with request.app.state.session_factory()`.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory() -> AsyncGenerator:
        yield mock_db

    return _factory


@pytest.fixture
def app_factory(mock_twilio, mock_temporal):
    """
    Returns a callable(mock_db, settings) -> FastAPI app with all external
    deps replaced by mocks. Suitable for API tests.
    """
    def _build(mock_db: AsyncMock, settings: Settings | None = None):
        if settings is None:
            settings = make_test_settings()

        # Import only the identity router to keep app slim for tests
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from elixir.domains.identity.api import router as identity_router
        from elixir.shared.exceptions import ElixirError
        from elixir.runtime.middleware import AuthMiddleware, RequestLoggingMiddleware

        app = FastAPI()
        app.state.settings = settings
        app.state.twilio = mock_twilio
        app.state.temporal_client = mock_temporal
        app.state.session_factory = _make_mock_session_factory(mock_db)

        app.add_middleware(RequestLoggingMiddleware)
        app.add_middleware(AuthMiddleware)
        app.include_router(identity_router, prefix="/auth")

        @app.exception_handler(ElixirError)
        async def elixir_handler(request: Request, exc: ElixirError) -> JSONResponse:
            return JSONResponse(
                status_code=exc.http_status,
                content={"error": exc.error_code, "detail": exc.detail},
            )

        from fastapi.exceptions import RequestValidationError
        @app.exception_handler(RequestValidationError)
        async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
            return JSONResponse(
                status_code=422,
                content={"error": "VALIDATION_ERROR", "detail": exc.errors()},
            )

        return app

    return _build


@pytest_asyncio.fixture
async def async_client(app_factory, mock_db):
    """Ready-to-use httpx AsyncClient connected to the test app."""
    app = app_factory(mock_db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
