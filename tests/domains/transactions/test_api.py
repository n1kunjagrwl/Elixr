"""
API-layer tests for the transactions domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The TransactionsService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from tests.conftest import (
    SESSION_ID,
    USER_ID,
    make_test_settings,
    make_get_request_context_override,
)
from elixir.platform.security import create_access_token


# ── App builder ────────────────────────────────────────────────────────────────


def _build_transactions_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the transactions service
    dependency so HTTP-layer behaviour can be tested independently of service
    logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager

    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    import elixir.domains.transactions.api as transactions_api
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
    app.include_router(transactions_api.router, prefix="/transactions")

    get_transactions_service = getattr(
        transactions_api, "get_transactions_service", None
    )
    if get_transactions_service is not None:
        app.dependency_overrides[get_transactions_service] = lambda: mock_service

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


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_transaction_item_response(**overrides) -> dict:
    defaults = dict(
        id=str(uuid.uuid4()),
        category_id=str(uuid.uuid4()),
        amount="1250.50",
        currency="INR",
        label="Butter Chicken",
        is_primary=True,
    )
    defaults.update(overrides)
    return defaults


def _make_transaction_summary_response(**overrides) -> dict:
    defaults = dict(
        id=str(uuid.uuid4()),
        account_id=str(uuid.uuid4()),
        account_kind="bank",
        amount="1250.50",
        currency="INR",
        date=date(2026, 4, 25).isoformat(),
        type="debit",
        source="manual",
        raw_description="Swiggy order",
        notes="Team lunch",
        account_name="HDFC Savings",
        primary_category_id=str(uuid.uuid4()),
        primary_category_name="Food & Dining",
        primary_category_icon="utensils",
        created_at=_iso_now(),
        updated_at=_iso_now(),
    )
    defaults.update(overrides)
    return defaults


def _make_transaction_response(**overrides) -> dict:
    defaults = dict(
        id=str(uuid.uuid4()),
        user_id=str(USER_ID),
        account_id=str(uuid.uuid4()),
        account_kind="bank",
        amount="1250.50",
        currency="INR",
        date=date(2026, 4, 25).isoformat(),
        type="debit",
        source="manual",
        raw_description="Swiggy order",
        notes="Team lunch",
        account_name="HDFC Savings",
        items=[
            _make_transaction_item_response(),
            _make_transaction_item_response(
                id=str(uuid.uuid4()),
                amount="250.00",
                label="Delivery fee",
                is_primary=False,
            ),
        ],
        created_at=_iso_now(),
        updated_at=_iso_now(),
    )
    defaults.update(overrides)
    return defaults


def _make_list_response(items: list[dict], **overrides) -> dict:
    defaults = dict(
        items=items,
        total=len(items),
        page=1,
        page_size=50,
    )
    defaults.update(overrides)
    return defaults


# ── GET /transactions ──────────────────────────────────────────────────────────


class TestGetTransactions:
    async def test_get_transactions_returns_200_with_paginated_results(self):
        """Authenticated GET /transactions → 200 with paginated transaction summaries."""
        settings = make_test_settings()
        response_obj = _make_list_response(
            [
                _make_transaction_summary_response(),
                _make_transaction_summary_response(
                    id=str(uuid.uuid4()),
                    raw_description="Salary credit",
                    type="credit",
                    source="statement_import",
                    account_kind="credit_card",
                ),
            ],
            total=2,
            page=1,
            page_size=50,
        )
        svc = _make_mock_service(list_transactions=AsyncMock(return_value=response_obj))
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/transactions", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert len(data["items"]) == 2
        assert data["items"][0]["raw_description"] == "Swiggy order"

    async def test_get_transactions_accepts_representative_filters(self):
        """
        List endpoint accepts documented search and filter query params and
        returns a paginated payload.
        """
        settings = make_test_settings()
        response_obj = _make_list_response(
            [_make_transaction_summary_response()],
            total=1,
            page=1,
            page_size=50,
        )
        svc = _make_mock_service(list_transactions=AsyncMock(return_value=response_obj))
        app = _build_transactions_app(svc, settings)
        account_id = str(uuid.uuid4())
        category_id = str(uuid.uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/transactions",
                params={
                    "date_from": "2026-04-01",
                    "date_to": "2026-04-30",
                    "account_id": account_id,
                    "type": "debit",
                    "source": "manual",
                    "category_id": category_id,
                    "search_text": "swiggy",
                    "page": 1,
                    "page_size": 50,
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        assert resp.json()["items"][0]["type"] == "debit"

    async def test_unauthenticated_request_returns_401(self):
        """No auth header → 401."""
        svc = _make_mock_service()
        app = _build_transactions_app(svc)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/transactions")

        assert resp.status_code == 401


# ── GET /transactions/{transaction_id} ────────────────────────────────────────


class TestGetTransaction:
    async def test_get_transaction_returns_200_with_items(self):
        """Authenticated GET /transactions/{id} → 200 with full transaction detail."""
        settings = make_test_settings()
        transaction_id = uuid.uuid4()
        response_obj = _make_transaction_response(id=str(transaction_id))
        svc = _make_mock_service(get_transaction=AsyncMock(return_value=response_obj))
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/transactions/{transaction_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(transaction_id)
        assert len(data["items"]) == 2
        assert data["items"][0]["is_primary"] is True

    async def test_get_transaction_not_found_returns_404(self):
        """Service raises TransactionNotFoundError → 404."""
        from elixir.shared.exceptions import TransactionNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            get_transaction=AsyncMock(side_effect=TransactionNotFoundError("Not found"))
        )
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/transactions/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "TRANSACTION_NOT_FOUND"


# ── POST /transactions ─────────────────────────────────────────────────────────


class TestPostTransaction:
    async def test_post_transaction_returns_201_with_manual_transaction(self):
        """Valid manual transaction body → 201 with created transaction."""
        settings = make_test_settings()
        response_obj = _make_transaction_response(source="manual")
        svc = _make_mock_service(add_transaction=AsyncMock(return_value=response_obj))
        app = _build_transactions_app(svc, settings)
        category_id = str(uuid.uuid4())

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/transactions",
                json={
                    "account_id": str(uuid.uuid4()),
                    "account_kind": "bank",
                    "amount": "1500.00",
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "debit",
                    "raw_description": "Swiggy order",
                    "notes": "Team lunch",
                    "items": [
                        {"category_id": category_id, "amount": "1500.00", "label": None}
                    ],
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["source"] == "manual"
        assert data["type"] == "debit"

    async def test_post_transaction_missing_items_returns_422(self):
        """At least one transaction item is required → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/transactions",
                json={
                    "account_id": str(uuid.uuid4()),
                    "account_kind": "bank",
                    "amount": "1500.00",
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "debit",
                    "raw_description": "Swiggy order",
                    "items": [],
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_post_transaction_zero_amount_returns_422(self):
        """Zero-amount manual transactions are rejected → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/transactions",
                json={
                    "account_id": str(uuid.uuid4()),
                    "account_kind": "bank",
                    "amount": "0.00",
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "debit",
                    "raw_description": "Cash adjustment",
                    "items": [
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "0.00",
                            "label": None,
                        }
                    ],
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_post_transaction_invalid_type_returns_422(self):
        """Invalid transaction type value → 422 Validation Error."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/transactions",
                json={
                    "account_id": str(uuid.uuid4()),
                    "account_kind": "bank",
                    "amount": "1500.00",
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "expense",
                    "raw_description": "Swiggy order",
                    "items": [
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "1500.00",
                            "label": None,
                        }
                    ],
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_post_transaction_item_amount_mismatch_returns_422(self):
        """Service raises ItemAmountMismatchError when split totals do not match → 422."""
        from elixir.shared.exceptions import ItemAmountMismatchError

        settings = make_test_settings()
        svc = _make_mock_service(
            add_transaction=AsyncMock(
                side_effect=ItemAmountMismatchError(
                    "Item amounts must sum to transaction amount"
                )
            )
        )
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/transactions",
                json={
                    "account_id": str(uuid.uuid4()),
                    "account_kind": "bank",
                    "amount": "1500.00",
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "debit",
                    "raw_description": "Amazon order",
                    "items": [
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "1000.00",
                            "label": "Headphones",
                        },
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "200.00",
                            "label": "Olive oil",
                        },
                    ],
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422
        assert resp.json()["error"] == "ITEM_AMOUNT_MISMATCH"


# ── PATCH /transactions/{transaction_id} ──────────────────────────────────────


class TestPatchTransaction:
    async def test_patch_transaction_returns_200_with_updated_transaction(self):
        """Valid partial update → 200 with updated transaction detail."""
        settings = make_test_settings()
        transaction_id = uuid.uuid4()
        response_obj = _make_transaction_response(
            id=str(transaction_id),
            notes="Updated note",
            type="transfer",
            items=[
                _make_transaction_item_response(
                    category_id=str(uuid.uuid4()),
                    amount="1500.00",
                    label=None,
                    is_primary=True,
                )
            ],
        )
        svc = _make_mock_service(edit_transaction=AsyncMock(return_value=response_obj))
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/transactions/{transaction_id}",
                json={
                    "notes": "Updated note",
                    "type": "transfer",
                    "items": [
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "1500.00",
                            "label": None,
                        }
                    ],
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated note"
        assert data["type"] == "transfer"

    async def test_patch_transaction_not_found_returns_404(self):
        """Service raises TransactionNotFoundError → 404."""
        from elixir.shared.exceptions import TransactionNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            edit_transaction=AsyncMock(
                side_effect=TransactionNotFoundError("Not found")
            )
        )
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/transactions/{uuid.uuid4()}",
                json={"notes": "Updated note"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "TRANSACTION_NOT_FOUND"

    async def test_patch_transaction_invalid_type_returns_422(self):
        """Invalid patch enum value → 422 Validation Error."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/transactions/{uuid.uuid4()}",
                json={"type": "expense"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_patch_transaction_item_amount_mismatch_returns_422(self):
        """Service raises ItemAmountMismatchError for invalid edited split totals → 422."""
        from elixir.shared.exceptions import ItemAmountMismatchError

        settings = make_test_settings()
        svc = _make_mock_service(
            edit_transaction=AsyncMock(
                side_effect=ItemAmountMismatchError(
                    "Item amounts must sum to transaction amount"
                )
            )
        )
        app = _build_transactions_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/transactions/{uuid.uuid4()}",
                json={
                    "items": [
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "1000.00",
                            "label": "Headphones",
                        },
                        {
                            "category_id": str(uuid.uuid4()),
                            "amount": "200.00",
                            "label": "Olive oil",
                        },
                    ]
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422
        assert resp.json()["error"] == "ITEM_AMOUNT_MISMATCH"
