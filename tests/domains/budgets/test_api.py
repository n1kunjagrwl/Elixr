"""
API-layer tests for the budgets domain.

Uses httpx.AsyncClient against a minimal FastAPI app with the BudgetsService
dependency overridden per test.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
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


def _build_budgets_app(mock_service, settings=None):
    """Build a minimal FastAPI app with BudgetsService overridden."""
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.budgets.api import router as budgets_router, get_budgets_service
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
    app.include_router(budgets_router, prefix="/budgets")

    app.dependency_overrides[get_budgets_service] = lambda: mock_service

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


def _make_goal_with_progress_response(**overrides):
    from elixir.domains.budgets.schemas import BudgetGoalWithProgress

    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        category_id=uuid.uuid4(),
        limit_amount=Decimal("10000.00"),
        currency="INR",
        period_type="monthly",
        period_anchor_day=None,
        custom_start=None,
        custom_end=None,
        rollover=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        current_spend=Decimal("0.00"),
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
    )
    defaults.update(overrides)
    return BudgetGoalWithProgress(**defaults)


# ── GET /budgets ───────────────────────────────────────────────────────────────


class TestGetBudgets:
    async def test_get_budgets_returns_200(self):
        """Authenticated GET /budgets → 200 with list of goals."""
        settings = make_test_settings()
        goals = [
            _make_goal_with_progress_response(),
            _make_goal_with_progress_response(),
        ]
        svc = _make_mock_service(list_goals=AsyncMock(return_value=goals))
        app = _build_budgets_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/budgets", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_unauthenticated_returns_401(self):
        """No auth header → 401."""
        svc = _make_mock_service()
        app = _build_budgets_app(svc)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/budgets")

        assert resp.status_code == 401


# ── POST /budgets ──────────────────────────────────────────────────────────────


class TestPostBudget:
    async def test_post_budget_returns_201(self):
        """Valid budget body → 201 with BudgetGoalWithProgress."""
        settings = make_test_settings()
        response_obj = _make_goal_with_progress_response()
        svc = _make_mock_service(create_goal=AsyncMock(return_value=response_obj))
        app = _build_budgets_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/budgets",
                json={
                    "category_id": str(uuid.uuid4()),
                    "limit_amount": "10000.00",
                    "period_type": "monthly",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["period_type"] == "monthly"

    async def test_post_budget_custom_no_dates_returns_422(self):
        """Custom period without dates → service raises InvalidPeriodConfigError → 422."""
        from elixir.shared.exceptions import InvalidPeriodConfigError

        settings = make_test_settings()
        svc = _make_mock_service(
            create_goal=AsyncMock(
                side_effect=InvalidPeriodConfigError("Custom period requires dates")
            )
        )
        app = _build_budgets_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/budgets",
                json={
                    "category_id": str(uuid.uuid4()),
                    "limit_amount": "5000.00",
                    "period_type": "custom",
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_PERIOD_CONFIG"


# ── GET /budgets/{id} ─────────────────────────────────────────────────────────


class TestGetBudget:
    async def test_get_budget_returns_200(self):
        """Authenticated GET /budgets/{id} → 200."""
        settings = make_test_settings()
        goal_id = uuid.uuid4()
        response_obj = _make_goal_with_progress_response(id=goal_id)
        svc = _make_mock_service(get_goal=AsyncMock(return_value=response_obj))
        app = _build_budgets_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/budgets/{goal_id}", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(goal_id)

    async def test_get_budget_not_found_returns_404(self):
        """GET /budgets/{id} when not found → 404."""
        from elixir.shared.exceptions import BudgetGoalNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            get_goal=AsyncMock(side_effect=BudgetGoalNotFoundError("Not found"))
        )
        app = _build_budgets_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                f"/budgets/{uuid.uuid4()}", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "BUDGET_GOAL_NOT_FOUND"


# ── PATCH /budgets/{id} ───────────────────────────────────────────────────────


class TestPatchBudget:
    async def test_patch_budget_returns_200(self):
        """Valid partial update → 200 with updated goal."""
        settings = make_test_settings()
        goal_id = uuid.uuid4()
        response_obj = _make_goal_with_progress_response(
            id=goal_id, limit_amount=Decimal("20000.00")
        )
        svc = _make_mock_service(edit_goal=AsyncMock(return_value=response_obj))
        app = _build_budgets_app(svc, settings)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/budgets/{goal_id}",
                json={"limit_amount": "20000.00"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(data["limit_amount"]) == Decimal("20000.00")


# ── DELETE /budgets/{id} ──────────────────────────────────────────────────────


class TestDeleteBudget:
    async def test_delete_budget_returns_204(self):
        """Successful deactivation → 204 No Content."""
        settings = make_test_settings()
        svc = _make_mock_service(deactivate_goal=AsyncMock(return_value=None))
        app = _build_budgets_app(svc, settings)
        goal_id = uuid.uuid4()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.delete(
                f"/budgets/{goal_id}", headers=_make_auth_header(settings)
            )

        assert resp.status_code == 204
