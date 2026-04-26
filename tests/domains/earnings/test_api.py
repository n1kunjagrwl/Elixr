"""
API-layer tests for the earnings domain.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from tests.conftest import SESSION_ID, USER_ID, make_test_settings
from elixir.shared.security import create_access_token


def _build_earnings_app(mock_service, settings=None):
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from elixir.domains.earnings.api import router as earnings_router, get_earnings_service
    from elixir.runtime.middleware import AuthMiddleware, RequestLoggingMiddleware
    from elixir.shared.exceptions import ElixirError

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
    app.include_router(earnings_router, prefix="/earnings")
    app.dependency_overrides[get_earnings_service] = lambda: mock_service

    @app.exception_handler(ElixirError)
    async def elixir_handler(request: Request, exc: ElixirError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": exc.detail},
        )

    def _serialisable(errors: list) -> list:
        safe = []
        for err in errors:
            entry = dict(err)
            if "ctx" in entry:
                ctx = dict(entry["ctx"])
                entry["ctx"] = {k: str(v) if isinstance(v, Exception) else v for k, v in ctx.items()}
            safe.append(entry)
        return safe

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "VALIDATION_ERROR", "detail": _serialisable(exc.errors())},
        )

    return app


def _make_auth_header(settings=None) -> dict[str, str]:
    if settings is None:
        settings = make_test_settings()
    token, _ = create_access_token(
        str(USER_ID), str(SESSION_ID),
        settings.jwt_secret, settings.access_token_expiry_minutes,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_mock_service(**overrides):
    svc = AsyncMock()
    for name, value in overrides.items():
        setattr(svc, name, value)
    return svc


def _make_source_response(**overrides) -> dict:
    defaults = dict(
        id=str(uuid.uuid4()),
        user_id=str(USER_ID),
        name="Think41 Salary",
        type="salary",
        is_active=True,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=None,
    )
    defaults.update(overrides)
    return defaults


def _make_earning_response(**overrides) -> dict:
    defaults = dict(
        id=str(uuid.uuid4()),
        user_id=str(USER_ID),
        transaction_id=None,
        source_id=None,
        source_type="salary",
        source_label="Think41 Salary",
        source_name="Think41 Salary",
        amount="100000.00",
        currency="INR",
        date=date(2026, 4, 25).isoformat(),
        notes="April salary",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=None,
    )
    defaults.update(overrides)
    return defaults


class TestSourcesApi:
    async def test_get_sources_returns_200(self):
        settings = make_test_settings()
        svc = _make_mock_service(list_sources=AsyncMock(return_value=[_make_source_response()]))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/earnings/sources", headers=_make_auth_header(settings))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_post_source_returns_201(self):
        settings = make_test_settings()
        svc = _make_mock_service(add_source=AsyncMock(return_value=_make_source_response()))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/earnings/sources",
                json={"name": "Think41 Salary", "type": "salary"},
                headers=_make_auth_header(settings),
            )
        assert resp.status_code == 201

    async def test_patch_source_returns_200(self):
        settings = make_test_settings()
        source_id = uuid.uuid4()
        svc = _make_mock_service(edit_source=AsyncMock(return_value=_make_source_response(id=str(source_id), name="Renamed")))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/earnings/sources/{source_id}",
                json={"name": "Renamed"},
                headers=_make_auth_header(settings),
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    async def test_delete_source_returns_204(self):
        settings = make_test_settings()
        source_id = uuid.uuid4()
        svc = _make_mock_service(deactivate_source=AsyncMock(return_value=None))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/earnings/sources/{source_id}",
                headers=_make_auth_header(settings),
            )
        assert resp.status_code == 204


class TestEarningsApi:
    async def test_get_earnings_returns_200(self):
        settings = make_test_settings()
        svc = _make_mock_service(list_earnings=AsyncMock(return_value=[_make_earning_response()]))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/earnings", headers=_make_auth_header(settings))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_post_earning_returns_201(self):
        settings = make_test_settings()
        svc = _make_mock_service(add_manual_earning=AsyncMock(return_value=_make_earning_response()))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/earnings",
                json={
                    "amount": "100000.00",
                    "currency": "INR",
                    "date": "2026-04-25",
                    "source_type": "salary",
                    "source_label": "Think41 Salary",
                },
                headers=_make_auth_header(settings),
            )
        assert resp.status_code == 201

    async def test_patch_earning_returns_200(self):
        settings = make_test_settings()
        earning_id = uuid.uuid4()
        svc = _make_mock_service(edit_earning=AsyncMock(return_value=_make_earning_response(id=str(earning_id), notes="Updated")))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/earnings/{earning_id}",
                json={"notes": "Updated"},
                headers=_make_auth_header(settings),
            )
        assert resp.status_code == 200

    async def test_classify_transaction_returns_200(self):
        settings = make_test_settings()
        svc = _make_mock_service(classify_transaction=AsyncMock(return_value=None))
        app = _build_earnings_app(svc, settings)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/earnings/classify/{uuid.uuid4()}",
                json={"classification": "income", "source_type": "salary", "source_label": "Think41 Salary"},
                headers=_make_auth_header(settings),
            )
        assert resp.status_code == 200

    async def test_unauthenticated_returns_401(self):
        svc = _make_mock_service()
        app = _build_earnings_app(svc)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/earnings")
        assert resp.status_code == 401
