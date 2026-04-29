"""
API-layer tests for the peers domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The PeersService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
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


def _build_peers_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the peers service dependency
    so HTTP-layer behaviour can be tested independently of service logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.peers.api import router as peers_router, get_peers_service
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
    app.include_router(peers_router, prefix="/peers")

    app.dependency_overrides[get_peers_service] = lambda: mock_service

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
                entry["ctx"] = {
                    k: str(v) if isinstance(v, Exception) else v for k, v in ctx.items()
                }
            safe.append(entry)
        return safe

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "detail": _serialisable(exc.errors()),
            },
        )

    return app


def _make_auth_header(settings=None) -> dict[str, str]:
    """Generate a valid Bearer token for USER_ID / SESSION_ID."""
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
    """Return a plain AsyncMock with method overrides applied."""
    svc = AsyncMock()
    for name, value in overrides.items():
        setattr(svc, name, value)
    return svc


def _make_contact_response(**overrides):
    from elixir.domains.peers.schemas import PeerContactResponse

    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        name="Alice",
        phone=None,
        notes=None,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return PeerContactResponse(**defaults)


def _make_balance_response(**overrides):
    from elixir.domains.peers.schemas import PeerBalanceResponse

    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        peer_id=uuid.uuid4(),
        description="Dinner split",
        original_amount=Decimal("500.00"),
        settled_amount=Decimal("0.00"),
        remaining_amount=Decimal("500.00"),
        currency="INR",
        direction="owed_to_me",
        status="open",
        linked_transaction_id=None,
        notes=None,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return PeerBalanceResponse(**defaults)


def _make_settlement_response(**overrides):
    from elixir.domains.peers.schemas import PeerSettlementResponse

    defaults = dict(
        id=uuid.uuid4(),
        balance_id=uuid.uuid4(),
        amount=Decimal("100.00"),
        currency="INR",
        settled_at=datetime.now(timezone.utc),
        method="cash",
        linked_transaction_id=None,
        notes=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return PeerSettlementResponse(**defaults)


# ── GET /peers/contacts ────────────────────────────────────────────────────────


class TestGetContacts:
    async def test_get_contacts_returns_200(self):
        """Authenticated GET /peers/contacts → 200 with contact list."""
        settings = make_test_settings()
        contacts = [_make_contact_response(), _make_contact_response(name="Bob")]
        svc = _make_mock_service(list_contacts=AsyncMock(return_value=contacts))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/peers/contacts", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_unauthenticated_returns_401(self):
        """No auth header → 401."""
        svc = _make_mock_service()
        app = _build_peers_app(svc)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/peers/contacts")

        assert resp.status_code == 401


# ── POST /peers/contacts ───────────────────────────────────────────────────────


class TestPostContact:
    async def test_post_contact_returns_201(self):
        """Valid contact body → 201 with PeerContactResponse."""
        settings = make_test_settings()
        response_obj = _make_contact_response(name="Charlie")
        svc = _make_mock_service(add_contact=AsyncMock(return_value=response_obj))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/peers/contacts",
                json={"name": "Charlie"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Charlie"

    async def test_post_contact_missing_name_returns_422(self):
        """Missing required name → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/peers/contacts",
                json={},  # no name
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── PATCH /peers/contacts/{id} ─────────────────────────────────────────────────


class TestPatchContact:
    async def test_patch_contact_returns_200(self):
        """Valid partial update → 200 with updated PeerContactResponse."""
        settings = make_test_settings()
        contact_id = uuid.uuid4()
        response_obj = _make_contact_response(id=contact_id, name="Updated Name")
        svc = _make_mock_service(edit_contact=AsyncMock(return_value=response_obj))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/peers/contacts/{contact_id}",
                json={"name": "Updated Name"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"

    async def test_patch_contact_not_found_returns_404(self):
        """Service raises PeerContactNotFoundError → 404."""
        from elixir.shared.exceptions import PeerContactNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            edit_contact=AsyncMock(side_effect=PeerContactNotFoundError("Not found"))
        )
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/peers/contacts/{uuid.uuid4()}",
                json={"name": "X"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "PEER_CONTACT_NOT_FOUND"


# ── DELETE /peers/contacts/{id} ────────────────────────────────────────────────


class TestDeleteContact:
    async def test_delete_contact_returns_204(self):
        """Successful contact deletion → 204 No Content."""
        settings = make_test_settings()
        svc = _make_mock_service(delete_contact=AsyncMock(return_value=None))
        app = _build_peers_app(svc, settings)
        contact_id = uuid.uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/peers/contacts/{contact_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204

    async def test_delete_contact_open_balances_returns_409(self):
        """Service raises ContactHasOpenBalancesError → 409."""
        from elixir.shared.exceptions import ContactHasOpenBalancesError

        settings = make_test_settings()
        svc = _make_mock_service(
            delete_contact=AsyncMock(
                side_effect=ContactHasOpenBalancesError("Has open balances")
            )
        )
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/peers/contacts/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 409
        assert resp.json()["error"] == "CONTACT_HAS_OPEN_BALANCES"


# ── GET /peers/balances ────────────────────────────────────────────────────────


class TestGetBalances:
    async def test_get_balances_returns_200(self):
        """Authenticated GET /peers/balances → 200 with balance list."""
        settings = make_test_settings()
        balances = [_make_balance_response(), _make_balance_response(direction="i_owe")]
        svc = _make_mock_service(list_balances=AsyncMock(return_value=balances))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/peers/balances", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_get_balances_with_status_filter(self):
        """GET /peers/balances?status=open → passes status filter to service."""
        settings = make_test_settings()
        balances = [_make_balance_response(status="open")]
        svc = _make_mock_service(list_balances=AsyncMock(return_value=balances))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/peers/balances?status=open",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        svc.list_balances.assert_called_once()


# ── POST /peers/balances ───────────────────────────────────────────────────────


class TestPostBalance:
    async def test_post_balance_returns_201(self):
        """Valid balance body → 201 with PeerBalanceResponse."""
        settings = make_test_settings()
        peer_id = uuid.uuid4()
        response_obj = _make_balance_response(peer_id=peer_id)
        svc = _make_mock_service(log_balance=AsyncMock(return_value=response_obj))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/peers/balances",
                json={
                    "peer_id": str(peer_id),
                    "description": "Dinner split",
                    "original_amount": "500.00",
                    "direction": "owed_to_me",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Dinner split"

    async def test_post_balance_invalid_direction_returns_422(self):
        """Invalid direction value → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_peers_app(svc, settings)
        peer_id = uuid.uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/peers/balances",
                json={
                    "peer_id": str(peer_id),
                    "description": "Dinner",
                    "original_amount": "500.00",
                    "direction": "invalid_direction",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── PATCH /peers/balances/{id} ─────────────────────────────────────────────────


class TestPatchBalance:
    async def test_patch_balance_returns_200(self):
        """Valid partial update on balance → 200 with updated PeerBalanceResponse."""
        settings = make_test_settings()
        balance_id = uuid.uuid4()
        response_obj = _make_balance_response(
            id=balance_id, description="Updated description"
        )
        svc = _make_mock_service(edit_balance=AsyncMock(return_value=response_obj))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/peers/balances/{balance_id}",
                json={"description": "Updated description"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Updated description"


# ── GET /peers/balances/{id}/settlements ───────────────────────────────────────


class TestGetSettlements:
    async def test_get_settlements_returns_200(self):
        """Authenticated GET /peers/balances/{id}/settlements → 200 with list."""
        settings = make_test_settings()
        balance_id = uuid.uuid4()
        settlements = [
            _make_settlement_response(balance_id=balance_id),
            _make_settlement_response(balance_id=balance_id, amount=Decimal("200.00")),
        ]
        svc = _make_mock_service(list_settlements=AsyncMock(return_value=settlements))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/peers/balances/{balance_id}/settlements",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2


# ── POST /peers/balances/{id}/settlements ──────────────────────────────────────


class TestPostSettlement:
    async def test_post_settlement_returns_201(self):
        """Valid settlement body → 201 with PeerSettlementResponse."""
        settings = make_test_settings()
        balance_id = uuid.uuid4()
        response_obj = _make_settlement_response(
            balance_id=balance_id, amount=Decimal("100.00")
        )
        svc = _make_mock_service(record_settlement=AsyncMock(return_value=response_obj))
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/peers/balances/{balance_id}/settlements",
                json={
                    "amount": "100.00",
                    "settled_at": datetime.now(timezone.utc).isoformat(),
                    "method": "cash",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert Decimal(data["amount"]) == Decimal("100.00")

    async def test_post_settlement_exceeds_remaining_returns_422(self):
        """Service raises SettlementExceedsRemainingError → 422."""
        from elixir.shared.exceptions import SettlementExceedsRemainingError

        settings = make_test_settings()
        balance_id = uuid.uuid4()
        svc = _make_mock_service(
            record_settlement=AsyncMock(
                side_effect=SettlementExceedsRemainingError("Exceeds remaining")
            )
        )
        app = _build_peers_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/peers/balances/{balance_id}/settlements",
                json={
                    "amount": "9999.00",
                    "settled_at": datetime.now(timezone.utc).isoformat(),
                    "method": "cash",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422
        assert resp.json()["error"] == "SETTLEMENT_EXCEEDS_REMAINING"
