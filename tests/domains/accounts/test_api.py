"""
API-layer tests for the accounts domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The AccountsService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
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


def _build_accounts_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the accounts service dependency
    so HTTP-layer behaviour can be tested independently of service logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.accounts.api import (
        router as accounts_router,
        get_accounts_service,
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
    app.include_router(accounts_router, prefix="/accounts")

    app.dependency_overrides[get_accounts_service] = lambda: mock_service

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


def _make_bank_account_response(**overrides):
    from elixir.domains.accounts.schemas import BankAccountResponse

    defaults = dict(
        id=uuid.uuid4(),
        nickname="My SBI Savings",
        bank_name="SBI",
        account_type="savings",
        last4="1234",
        currency="INR",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return BankAccountResponse(**defaults)


def _make_credit_card_response(**overrides):
    from elixir.domains.accounts.schemas import CreditCardResponse

    defaults = dict(
        id=uuid.uuid4(),
        nickname="My HDFC CC",
        bank_name="HDFC",
        card_network="visa",
        last4="5678",
        credit_limit=None,
        billing_cycle_day=None,
        currency="INR",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return CreditCardResponse(**defaults)


def _make_account_summary_response(account_kind="bank", **overrides):
    from elixir.domains.accounts.schemas import AccountSummaryResponse

    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        nickname="Test Account",
        bank_name="SBI",
        account_kind=account_kind,
        subtype="savings",
        last4="1234",
        currency="INR",
        is_active=True,
    )
    defaults.update(overrides)
    return AccountSummaryResponse(**defaults)


# ── GET /accounts ──────────────────────────────────────────────────────────────


class TestGetAccounts:
    async def test_get_accounts_returns_200_with_list(self):
        """Authenticated GET /accounts → 200 with account list."""
        settings = make_test_settings()
        accounts = [
            _make_account_summary_response("bank"),
            _make_account_summary_response("credit_card"),
        ]
        svc = _make_mock_service(list_accounts=AsyncMock(return_value=accounts))
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/accounts", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_unauthenticated_request_returns_401(self):
        """No auth header → 401."""
        svc = _make_mock_service()
        app = _build_accounts_app(svc)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/accounts")  # no auth

        assert resp.status_code == 401


# ── POST /accounts/bank ────────────────────────────────────────────────────────


class TestPostBankAccount:
    async def test_post_bank_returns_201_with_account(self):
        """Valid bank account body → 201 with BankAccountResponse."""
        settings = make_test_settings()
        response_obj = _make_bank_account_response()
        svc = _make_mock_service(add_bank_account=AsyncMock(return_value=response_obj))
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/accounts/bank",
                json={
                    "nickname": "My SBI Savings",
                    "bank_name": "SBI",
                    "account_type": "savings",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["nickname"] == "My SBI Savings"
        assert data["account_type"] == "savings"

    async def test_post_bank_invalid_type_returns_422(self):
        """Invalid account_type value → 422 Validation Error."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/accounts/bank",
                json={
                    "nickname": "Test",
                    "bank_name": "SBI",
                    "account_type": "invalid_type",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_post_bank_missing_required_fields_returns_422(self):
        """Missing required fields → 422."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/accounts/bank",
                json={"nickname": "Test"},  # missing bank_name and account_type
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── POST /accounts/credit-cards ───────────────────────────────────────────────


class TestPostCreditCard:
    async def test_post_credit_card_returns_201(self):
        """Valid credit card body → 201 with CreditCardResponse."""
        settings = make_test_settings()
        response_obj = _make_credit_card_response()
        svc = _make_mock_service(add_credit_card=AsyncMock(return_value=response_obj))
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/accounts/credit-cards",
                json={
                    "nickname": "My HDFC CC",
                    "bank_name": "HDFC",
                    "card_network": "visa",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["nickname"] == "My HDFC CC"

    async def test_post_credit_card_invalid_billing_cycle_day_returns_422(self):
        """billing_cycle_day > 28 → 422 Validation Error."""
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/accounts/credit-cards",
                json={
                    "nickname": "Test",
                    "bank_name": "HDFC",
                    "billing_cycle_day": 29,
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


# ── PATCH /accounts/bank/{id} ─────────────────────────────────────────────────


class TestPatchBankAccount:
    async def test_patch_bank_returns_200_with_updated(self):
        """Valid partial update → 200 with updated BankAccountResponse."""
        settings = make_test_settings()
        account_id = uuid.uuid4()
        response_obj = _make_bank_account_response(
            id=account_id, nickname="Updated Name"
        )
        svc = _make_mock_service(edit_bank_account=AsyncMock(return_value=response_obj))
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/accounts/bank/{account_id}",
                json={"nickname": "Updated Name"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["nickname"] == "Updated Name"

    async def test_patch_bank_not_found_returns_404(self):
        """Service raises AccountNotFoundError → 404."""
        from elixir.shared.exceptions import AccountNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            edit_bank_account=AsyncMock(side_effect=AccountNotFoundError("Not found"))
        )
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/accounts/bank/{uuid.uuid4()}",
                json={"nickname": "New Name"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "ACCOUNT_NOT_FOUND"


# ── DELETE /accounts/bank/{id} ────────────────────────────────────────────────


class TestDeleteBankAccount:
    async def test_delete_bank_returns_204(self):
        """Successful deactivation → 204 No Content."""
        settings = make_test_settings()
        svc = _make_mock_service(deactivate_bank_account=AsyncMock(return_value=None))
        app = _build_accounts_app(svc, settings)
        account_id = uuid.uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/accounts/bank/{account_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204

    async def test_delete_bank_wrong_user_returns_403(self):
        """Service raises AccountBelongsToAnotherUserError → 403."""
        from elixir.shared.exceptions import AccountBelongsToAnotherUserError

        settings = make_test_settings()
        svc = _make_mock_service(
            deactivate_bank_account=AsyncMock(
                side_effect=AccountBelongsToAnotherUserError("Forbidden")
            )
        )
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/accounts/bank/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 403

    async def test_delete_bank_not_found_returns_404(self):
        """Service raises AccountNotFoundError → 404."""
        from elixir.shared.exceptions import AccountNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            deactivate_bank_account=AsyncMock(
                side_effect=AccountNotFoundError("Not found")
            )
        )
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/accounts/bank/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404


# ── PATCH /accounts/credit-cards/{id} ────────────────────────────────────────


class TestPatchCreditCard:
    async def test_patch_credit_card_returns_200(self):
        """Valid partial update on credit card → 200."""
        settings = make_test_settings()
        card_id = uuid.uuid4()
        response_obj = _make_credit_card_response(id=card_id, nickname="Updated CC")
        svc = _make_mock_service(edit_credit_card=AsyncMock(return_value=response_obj))
        app = _build_accounts_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/accounts/credit-cards/{card_id}",
                json={"nickname": "Updated CC"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        assert resp.json()["nickname"] == "Updated CC"


# ── DELETE /accounts/credit-cards/{id} ────────────────────────────────────────


class TestDeleteCreditCard:
    async def test_delete_credit_card_returns_204(self):
        """Successful deactivation of a credit card → 204."""
        settings = make_test_settings()
        svc = _make_mock_service(deactivate_credit_card=AsyncMock(return_value=None))
        app = _build_accounts_app(svc, settings)
        card_id = uuid.uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/accounts/credit-cards/{card_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204
