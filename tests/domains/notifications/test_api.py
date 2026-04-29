"""
API-layer tests for the notifications domain.

Uses httpx.AsyncClient against a minimal FastAPI app with the
NotificationsService dependency overridden per test.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from tests.conftest import (
    USER_ID,
    SESSION_ID,
    make_test_settings,
    make_get_request_context_override,
)
from elixir.platform.security import create_access_token


# ── App builder ────────────────────────────────────────────────────────────────


def _build_notifications_app(mock_service, settings=None):
    """Build a minimal FastAPI app with NotificationsService overridden."""
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.notifications.api import (
        router as notifications_router,
        get_notifications_service,
    )
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
    app.state.session_factory = _factory

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    app.include_router(notifications_router, prefix="/notifications")

    app.dependency_overrides[get_notifications_service] = lambda: mock_service

    dep_key, override_fn = make_get_request_context_override(mock_db)
    app.dependency_overrides[dep_key] = override_fn

    @app.exception_handler(ElixirError)
    async def elixir_handler(request: Request, exc: ElixirError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "VALIDATION_ERROR", "detail": exc.errors()},
        )

    return app


def _make_auth_header(settings=None) -> dict[str, str]:
    if settings is None:
        settings = make_test_settings()
    token, _ = create_access_token(
        str(USER_ID),
        str(SESSION_ID),
        settings.jwt_secret,
        settings.access_token_expiry_minutes,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_mock_service(**overrides):
    svc = AsyncMock()
    for name, value in overrides.items():
        setattr(svc, name, value)
    return svc


def _make_notification_response(**overrides):
    from elixir.domains.notifications.schemas import NotificationResponse

    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        type="accounts.AccountLinked",
        title="Account added",
        body="Upload a statement to start tracking.",
        route="/statements/upload",
        primary_entity_id=uuid.uuid4(),
        secondary_entity_id=None,
        period_start=None,
        read_at=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return NotificationResponse(**defaults)


# ── GET /notifications ─────────────────────────────────────────────────────────


class TestListNotifications:
    async def test_list_notifications_200(self):
        """Authenticated GET /notifications returns 200 with notification list."""
        settings = make_test_settings()
        notifications = [_make_notification_response(), _make_notification_response()]
        svc = _make_mock_service(
            list_notifications=AsyncMock(return_value=notifications)
        )
        app = _build_notifications_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/notifications", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_list_notifications_unread_200(self):
        """GET /notifications?unread=true passes unread_only=True to service."""
        settings = make_test_settings()
        mock_list = AsyncMock(return_value=[])
        svc = _make_mock_service(list_notifications=mock_list)
        app = _build_notifications_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/notifications?unread=true",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        # Verify service was called with unread_only=True
        call_kwargs = mock_list.call_args
        assert call_kwargs is not None
        # unread_only=True should be passed (either positionally or as kwarg)
        args, kwargs = call_kwargs
        passed_unread = kwargs.get("unread_only", args[1] if len(args) > 1 else False)
        assert passed_unread is True


# ── PATCH /notifications/{id}/read ────────────────────────────────────────────


class TestMarkRead:
    async def test_mark_read_200(self):
        """PATCH /notifications/{id}/read returns 200."""
        settings = make_test_settings()
        notification_id = uuid.uuid4()
        svc = _make_mock_service(mark_read=AsyncMock(return_value=None))
        app = _build_notifications_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/notifications/{notification_id}/read",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200

    async def test_mark_read_not_found_404(self):
        """Service raises NotificationNotFoundError -> 404."""
        from elixir.shared.exceptions import NotificationNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            mark_read=AsyncMock(side_effect=NotificationNotFoundError("Not found"))
        )
        app = _build_notifications_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/notifications/{uuid.uuid4()}/read",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "NOTIFICATION_NOT_FOUND"


# ── PATCH /notifications/read-all ─────────────────────────────────────────────


class TestMarkAllRead:
    async def test_mark_all_read_200(self):
        """PATCH /notifications/read-all returns {'marked': N}."""
        settings = make_test_settings()
        svc = _make_mock_service(mark_all_read=AsyncMock(return_value={"marked": 3}))
        app = _build_notifications_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                "/notifications/read-all",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        assert resp.json() == {"marked": 3}
