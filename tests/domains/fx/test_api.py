"""
API-layer tests for the fx domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The FXService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from tests.conftest import USER_ID, SESSION_ID, make_test_settings, make_get_request_context_override
from elixir.platform.security import create_access_token


# ── App builder ────────────────────────────────────────────────────────────────

def _build_fx_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the fx service dependency
    so HTTP-layer behaviour can be tested independently of service logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.fx.api import router as fx_router, get_fx_service
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
    app.include_router(fx_router, prefix="/fx")

    app.dependency_overrides[get_fx_service] = lambda: mock_service

    dep_key, override_fn = make_get_request_context_override(mock_db)
    app.dependency_overrides[dep_key] = override_fn

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
    """Generate a valid Bearer token for USER_ID / SESSION_ID."""
    if settings is None:
        settings = make_test_settings()
    token, _ = create_access_token(
        str(USER_ID), str(SESSION_ID),
        settings.jwt_secret, settings.access_token_expiry_minutes,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_mock_service(**overrides):
    """Return a plain AsyncMock with method overrides applied."""
    svc = AsyncMock()
    for name, value in overrides.items():
        setattr(svc, name, value)
    return svc


def _make_fx_rate_response(**overrides):
    from elixir.domains.fx.schemas import FXRateResponse

    defaults = dict(
        from_currency="USD",
        to_currency="INR",
        rate=Decimal("83.500000"),
        fetched_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return FXRateResponse(**defaults)


def _make_convert_response(**overrides):
    from elixir.domains.fx.schemas import ConvertResponse

    defaults = dict(
        from_currency="USD",
        to_currency="INR",
        original_amount=Decimal("100.00"),
        converted_amount=Decimal("8350.00"),
        rate_used=Decimal("83.500000"),
        fetched_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return ConvertResponse(**defaults)


# ── GET /fx/rates ──────────────────────────────────────────────────────────────

class TestGetRates:
    async def test_get_rates_returns_200_with_list(self):
        """Authenticated GET /fx/rates → 200 with rate list."""
        settings = make_test_settings()
        rates = [
            _make_fx_rate_response(from_currency="USD", to_currency="INR"),
            _make_fx_rate_response(from_currency="EUR", to_currency="INR"),
        ]
        svc = _make_mock_service(list_rates=AsyncMock(return_value=rates))
        app = _build_fx_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/fx/rates", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["from_currency"] == "USD"
        assert data[1]["from_currency"] == "EUR"

    async def test_get_rates_empty_returns_200_empty_list(self):
        """When no rates cached, GET /fx/rates → 200 with empty list."""
        settings = make_test_settings()
        svc = _make_mock_service(list_rates=AsyncMock(return_value=[]))
        app = _build_fx_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/fx/rates", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /fx/convert ────────────────────────────────────────────────────────────

class TestGetConvert:
    async def test_get_convert_returns_200_with_result(self):
        """Valid convert query → 200 with ConvertResponse."""
        settings = make_test_settings()
        response_obj = _make_convert_response()
        svc = _make_mock_service(convert_with_meta=AsyncMock(return_value=response_obj))
        app = _build_fx_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/fx/convert",
                params={"amount": "100.00", "from": "USD", "to": "INR"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["from_currency"] == "USD"
        assert data["to_currency"] == "INR"
        assert "converted_amount" in data

    async def test_get_convert_no_rate_returns_503(self):
        """Service raises FXRateUnavailableError → 503 (mapped in API layer)."""
        from elixir.shared.exceptions import FXRateUnavailableError

        settings = make_test_settings()
        svc = _make_mock_service(
            convert_with_meta=AsyncMock(
                side_effect=FXRateUnavailableError("No rate for USD/XYZ")
            )
        )
        app = _build_fx_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/fx/convert",
                params={"amount": "100.00", "from": "USD", "to": "XYZ"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 503
        assert resp.json()["error"] == "FX_RATE_UNAVAILABLE"

    async def test_get_convert_same_currency_returns_amount(self):
        """Converting same currency → 200 with original_amount == converted_amount."""
        settings = make_test_settings()
        response_obj = _make_convert_response(
            from_currency="INR",
            to_currency="INR",
            original_amount=Decimal("100.00"),
            converted_amount=Decimal("100.00"),
            rate_used=Decimal("1.000000"),
        )
        svc = _make_mock_service(convert_with_meta=AsyncMock(return_value=response_obj))
        app = _build_fx_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/fx/convert",
                params={"amount": "100.00", "from": "INR", "to": "INR"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(data["original_amount"]) == Decimal(data["converted_amount"])

    async def test_get_convert_missing_params_returns_422(self):
        """Missing required query params → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_fx_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/fx/convert",
                params={"amount": "100.00"},  # missing from and to
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── Auth guard ────────────────────────────────────────────────────────────────

class TestAuthRequired:
    async def test_unauthenticated_get_rates_returns_401(self):
        """No auth header on GET /fx/rates → 401."""
        svc = _make_mock_service()
        app = _build_fx_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/fx/rates")

        assert resp.status_code == 401

    async def test_unauthenticated_get_convert_returns_401(self):
        """No auth header on GET /fx/convert → 401."""
        svc = _make_mock_service()
        app = _build_fx_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/fx/convert", params={"amount": "100", "from": "USD", "to": "INR"}
            )

        assert resp.status_code == 401
