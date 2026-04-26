"""
API-layer tests for the investments domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The InvestmentsService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import USER_ID, SESSION_ID, make_test_settings, make_get_request_context_override
from elixir.platform.security import create_access_token


# ── App builder ────────────────────────────────────────────────────────────────

def _build_investments_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the investments service dependency
    so HTTP-layer behaviour can be tested independently of service logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.investments.api import router as investments_router, get_investments_service
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
    app.include_router(investments_router, prefix="/investments")

    app.dependency_overrides[get_investments_service] = lambda: mock_service

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


def _make_instrument_response(**overrides):
    from elixir.domains.investments.schemas import InstrumentResponse
    defaults = dict(
        id=uuid.uuid4(),
        name="Reliance Industries",
        ticker="RELIANCE",
        isin=None,
        type="stock",
        exchange="NSE",
        currency="INR",
        data_source="eodhd",
        govt_rate_percent=None,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return InstrumentResponse(**defaults)


def _make_holding_response(**overrides):
    from elixir.domains.investments.schemas import HoldingResponse
    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        instrument_id=uuid.uuid4(),
        units=Decimal("10.000000"),
        avg_cost_per_unit=Decimal("2500.0000"),
        total_invested=Decimal("25000.00"),
        current_value=Decimal("27000.00"),
        current_price=Decimal("2700.0000"),
        last_valued_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return HoldingResponse(**defaults)


def _make_sip_response(**overrides):
    from elixir.domains.investments.schemas import SIPResponse
    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        instrument_id=uuid.uuid4(),
        amount=Decimal("5000.00"),
        frequency="monthly",
        debit_day=5,
        bank_account_id=uuid.uuid4(),
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return SIPResponse(**defaults)


def _make_fd_response(**overrides):
    from elixir.domains.investments.schemas import FDDetailsResponse
    defaults = dict(
        id=uuid.uuid4(),
        holding_id=uuid.uuid4(),
        principal=Decimal("100000.00"),
        rate_percent=Decimal("7.000"),
        tenure_days=365,
        start_date=date(2024, 1, 1),
        maturity_date=date(2025, 1, 1),
        compounding="quarterly",
        maturity_amount=Decimal("107185.90"),
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return FDDetailsResponse(**defaults)


# ── GET /investments/instruments ───────────────────────────────────────────────

class TestGetInstruments:
    async def test_get_instruments_returns_200(self):
        """Authenticated GET /investments/instruments → 200 with instrument list."""
        settings = make_test_settings()
        instruments = [_make_instrument_response()]
        svc = _make_mock_service(search_instruments=AsyncMock(return_value=instruments))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/investments/instruments",
                params={"q": "Reliance"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Reliance Industries"


# ── POST /investments/instruments ──────────────────────────────────────────────

class TestPostInstrument:
    async def test_post_instrument_returns_201(self):
        """Valid instrument body → 201 with InstrumentResponse."""
        settings = make_test_settings()
        instrument = _make_instrument_response()
        svc = _make_mock_service(create_instrument=AsyncMock(return_value=instrument))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/instruments",
                json={"name": "Reliance Industries", "type": "stock", "currency": "INR"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Reliance Industries"

    async def test_post_instrument_missing_required_returns_422(self):
        """Missing required fields → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/instruments",
                json={"ticker": "RELIANCE"},  # missing name, type, currency
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── GET /investments/holdings ──────────────────────────────────────────────────

class TestGetHoldings:
    async def test_get_holdings_returns_200(self):
        """Authenticated GET /investments/holdings → 200 with holding list."""
        settings = make_test_settings()
        holdings = [_make_holding_response(), _make_holding_response()]
        svc = _make_mock_service(list_holdings=AsyncMock(return_value=holdings))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/investments/holdings",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2


# ── POST /investments/holdings ─────────────────────────────────────────────────

class TestPostHolding:
    async def test_post_holding_returns_201(self):
        """Valid holding body → 201 with HoldingResponse."""
        settings = make_test_settings()
        instrument_id = uuid.uuid4()
        holding = _make_holding_response(instrument_id=instrument_id)
        svc = _make_mock_service(add_holding=AsyncMock(return_value=holding))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/holdings",
                json={"instrument_id": str(instrument_id)},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201

    async def test_post_holding_duplicate_returns_409(self):
        """DuplicateHoldingError from service → 409."""
        from elixir.shared.exceptions import DuplicateHoldingError

        settings = make_test_settings()
        svc = _make_mock_service(
            add_holding=AsyncMock(side_effect=DuplicateHoldingError("Already exists"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/holdings",
                json={"instrument_id": str(uuid.uuid4())},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 409

    async def test_post_holding_instrument_not_found_returns_404(self):
        """InstrumentNotFoundError from service → 404."""
        from elixir.shared.exceptions import InstrumentNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            add_holding=AsyncMock(side_effect=InstrumentNotFoundError("Not found"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/holdings",
                json={"instrument_id": str(uuid.uuid4())},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── PATCH /investments/holdings/{id} ──────────────────────────────────────────

class TestPatchHolding:
    async def test_patch_holding_returns_200(self):
        """Valid partial update → 200 with HoldingResponse."""
        settings = make_test_settings()
        holding_id = uuid.uuid4()
        holding = _make_holding_response(id=holding_id)
        svc = _make_mock_service(edit_holding=AsyncMock(return_value=holding))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/investments/holdings/{holding_id}",
                json={"units": "15.000000"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200

    async def test_patch_holding_not_found_returns_404(self):
        """HoldingNotFoundError → 404."""
        from elixir.shared.exceptions import HoldingNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            edit_holding=AsyncMock(side_effect=HoldingNotFoundError("Not found"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/investments/holdings/{uuid.uuid4()}",
                json={"units": "15.000000"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── DELETE /investments/holdings/{id} ─────────────────────────────────────────

class TestDeleteHolding:
    async def test_delete_holding_returns_204(self):
        """Successful removal → 204 No Content."""
        settings = make_test_settings()
        svc = _make_mock_service(remove_holding=AsyncMock(return_value=None))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/investments/holdings/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204

    async def test_delete_holding_not_found_returns_404(self):
        """HoldingNotFoundError → 404."""
        from elixir.shared.exceptions import HoldingNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            remove_holding=AsyncMock(side_effect=HoldingNotFoundError("Not found"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/investments/holdings/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── POST /investments/holdings/{holding_id}/fd ────────────────────────────────

class TestPostFDDetails:
    async def test_post_fd_details_returns_201(self):
        """Valid FD body → 201 with FDDetailsResponse."""
        settings = make_test_settings()
        holding_id = uuid.uuid4()
        fd = _make_fd_response(holding_id=holding_id)
        svc = _make_mock_service(add_fd_details=AsyncMock(return_value=fd))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/investments/holdings/{holding_id}/fd",
                json={
                    "principal": "100000.00",
                    "rate_percent": "7.000",
                    "tenure_days": 365,
                    "start_date": "2024-01-01",
                    "maturity_date": "2025-01-01",
                    "compounding": "quarterly",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201

    async def test_post_fd_details_non_fd_holding_returns_422(self):
        """FDDetailsRequiredError from service → 422."""
        from elixir.shared.exceptions import FDDetailsRequiredError

        settings = make_test_settings()
        svc = _make_mock_service(
            add_fd_details=AsyncMock(side_effect=FDDetailsRequiredError("Not FD"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/investments/holdings/{uuid.uuid4()}/fd",
                json={
                    "principal": "100000.00",
                    "rate_percent": "7.000",
                    "tenure_days": 365,
                    "start_date": "2024-01-01",
                    "maturity_date": "2025-01-01",
                    "compounding": "quarterly",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_post_fd_details_already_exists_returns_409(self):
        """FDDetailsAlreadyExistError → 409."""
        from elixir.shared.exceptions import FDDetailsAlreadyExistError

        settings = make_test_settings()
        svc = _make_mock_service(
            add_fd_details=AsyncMock(side_effect=FDDetailsAlreadyExistError("Already exists"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/investments/holdings/{uuid.uuid4()}/fd",
                json={
                    "principal": "100000.00",
                    "rate_percent": "7.000",
                    "tenure_days": 365,
                    "start_date": "2024-01-01",
                    "maturity_date": "2025-01-01",
                    "compounding": "quarterly",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 409


# ── GET /investments/history ───────────────────────────────────────────────────

class TestGetHistory:
    async def test_get_history_returns_200(self):
        """Authenticated GET /investments/history → 200 with snapshot list."""
        settings = make_test_settings()
        snapshots = [
            {"snapshot_date": "2024-01-01", "total_value": "100000.00"},
        ]
        svc = _make_mock_service(get_portfolio_history=AsyncMock(return_value=snapshots))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/investments/history",
                params={"from_date": "2024-01-01", "to_date": "2024-01-31"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1


# ── GET /investments/sip ───────────────────────────────────────────────────────

class TestGetSIPs:
    async def test_get_sips_returns_200(self):
        """Authenticated GET /investments/sip → 200 with SIP list."""
        settings = make_test_settings()
        sips = [_make_sip_response(), _make_sip_response()]
        svc = _make_mock_service(list_sips=AsyncMock(return_value=sips))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/investments/sip",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2


# ── POST /investments/sip ──────────────────────────────────────────────────────

class TestPostSIP:
    async def test_post_sip_returns_201(self):
        """Valid SIP registration body → 201 with SIPResponse."""
        settings = make_test_settings()
        sip = _make_sip_response()
        svc = _make_mock_service(register_sip=AsyncMock(return_value=sip))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/sip",
                json={
                    "instrument_id": str(uuid.uuid4()),
                    "amount": "5000.00",
                    "frequency": "monthly",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201

    async def test_post_sip_invalid_frequency_returns_422(self):
        """Invalid frequency → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/investments/sip",
                json={
                    "instrument_id": str(uuid.uuid4()),
                    "amount": "5000.00",
                    "frequency": "daily",  # not in enum
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── PATCH /investments/sip/{id} ───────────────────────────────────────────────

class TestPatchSIP:
    async def test_patch_sip_returns_200(self):
        """Valid partial SIP update → 200."""
        settings = make_test_settings()
        sip_id = uuid.uuid4()
        sip = _make_sip_response(id=sip_id)
        svc = _make_mock_service(edit_sip=AsyncMock(return_value=sip))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/investments/sip/{sip_id}",
                json={"amount": "7500.00"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200

    async def test_patch_sip_not_found_returns_404(self):
        """SIPNotFoundError → 404."""
        from elixir.shared.exceptions import SIPNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            edit_sip=AsyncMock(side_effect=SIPNotFoundError("Not found"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/investments/sip/{uuid.uuid4()}",
                json={"amount": "7500.00"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── DELETE /investments/sip/{id} ──────────────────────────────────────────────

class TestDeleteSIP:
    async def test_delete_sip_returns_204(self):
        """Successful SIP deactivation → 204."""
        settings = make_test_settings()
        svc = _make_mock_service(deactivate_sip=AsyncMock(return_value=None))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/investments/sip/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204

    async def test_delete_sip_not_found_returns_404(self):
        """SIPNotFoundError → 404."""
        from elixir.shared.exceptions import SIPNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            deactivate_sip=AsyncMock(side_effect=SIPNotFoundError("Not found"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/investments/sip/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── POST /investments/sip/{id}/confirm ────────────────────────────────────────

class TestConfirmSIP:
    async def test_confirm_sip_returns_200(self):
        """Valid confirm SIP body → 200."""
        settings = make_test_settings()
        sip_id = uuid.uuid4()
        transaction_id = uuid.uuid4()
        svc = _make_mock_service(confirm_sip_link=AsyncMock(return_value=None))
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/investments/sip/{sip_id}/confirm",
                json={"transaction_id": str(transaction_id)},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200

    async def test_confirm_sip_not_found_returns_404(self):
        """SIPNotFoundError → 404."""
        from elixir.shared.exceptions import SIPNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            confirm_sip_link=AsyncMock(side_effect=SIPNotFoundError("Not found"))
        )
        app = _build_investments_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/investments/sip/{uuid.uuid4()}/confirm",
                json={"transaction_id": str(uuid.uuid4())},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── Auth guard tests ───────────────────────────────────────────────────────────

class TestUnauthenticated:
    async def test_unauthenticated_returns_401(self):
        """No auth header → 401 for all investments endpoints."""
        svc = _make_mock_service()
        app = _build_investments_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/investments/holdings")

        assert resp.status_code == 401
