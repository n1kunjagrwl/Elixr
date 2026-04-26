"""
API-layer tests for the categorization domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The CategorizationService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import USER_ID, SESSION_ID, make_test_settings, make_get_request_context_override
from elixir.platform.security import create_access_token


# ── App builder ─────────────────────────────────────────────────────────────────

def _build_cat_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app with both categorization routers and
    the service dependency overridden.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.categorization.api import (
        router as cat_router,
        rules_router as cat_rules_router,
        get_categorization_service,
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
    app.include_router(cat_router, prefix="/categories")
    app.include_router(cat_rules_router, prefix="/categorization-rules")

    app.dependency_overrides[get_categorization_service] = lambda: mock_service

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


def _make_category_response(**overrides):
    from elixir.domains.categorization.schemas import CategoryResponse
    defaults = dict(
        id=uuid.uuid4(),
        name="Food & Dining",
        slug="food-dining",
        kind="expense",
        icon=None,
        is_default=False,
        parent_id=None,
        user_id=USER_ID,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return CategoryResponse(**defaults)


def _make_rule_response(**overrides):
    from elixir.domains.categorization.schemas import RuleResponse
    defaults = dict(
        id=uuid.uuid4(),
        user_id=USER_ID,
        pattern="zomato",
        match_type="contains",
        category_id=uuid.uuid4(),
        priority=0,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )
    defaults.update(overrides)
    return RuleResponse(**defaults)


# ── GET /categories ────────────────────────────────────────────────────────────

class TestGetCategories:
    async def test_get_categories_returns_200_with_list(self):
        """Authenticated GET /categories → 200 with category list."""
        settings = make_test_settings()
        categories = [
            _make_category_response(name="Food & Dining", is_default=True, user_id=None),
            _make_category_response(name="My Custom", is_default=False, user_id=USER_ID),
        ]
        svc = _make_mock_service(list_categories=AsyncMock(return_value=categories))
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/categories", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_unauthenticated_returns_401(self):
        """No auth header → 401."""
        svc = _make_mock_service()
        app = _build_cat_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/categories")

        assert resp.status_code == 401


# ── POST /categories ───────────────────────────────────────────────────────────

class TestPostCategory:
    async def test_post_category_returns_201(self):
        """Valid category body → 201 with CategoryResponse."""
        settings = make_test_settings()
        response_obj = _make_category_response(name="My Dining", slug="my-dining")
        svc = _make_mock_service(create_category=AsyncMock(return_value=response_obj))
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/categories",
                json={"name": "My Dining", "slug": "my-dining", "kind": "expense"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Dining"

    async def test_post_category_transfer_kind_returns_403(self):
        """Creating a category with kind='transfer' → 403."""
        from elixir.shared.exceptions import CategoryKindForbiddenError

        settings = make_test_settings()
        svc = _make_mock_service(
            create_category=AsyncMock(side_effect=CategoryKindForbiddenError("Transfer categories not allowed"))
        )
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/categories",
                json={"name": "My Transfer", "slug": "my-transfer", "kind": "transfer"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 403
        assert resp.json()["error"] == "CATEGORY_KIND_FORBIDDEN"


# ── PATCH /categories/{id} ─────────────────────────────────────────────────────

class TestPatchCategory:
    async def test_patch_category_default_returns_403(self):
        """Editing a default category → 403."""
        from elixir.shared.exceptions import CannotEditDefaultCategoryError

        settings = make_test_settings()
        cat_id = uuid.uuid4()
        svc = _make_mock_service(
            update_category=AsyncMock(side_effect=CannotEditDefaultCategoryError("Cannot edit defaults"))
        )
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/categories/{cat_id}",
                json={"name": "New Name"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 403
        assert resp.json()["error"] == "CANNOT_EDIT_DEFAULT_CATEGORY"

    async def test_patch_category_not_found_returns_404(self):
        """Category not found → 404."""
        from elixir.shared.exceptions import CategoryNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            update_category=AsyncMock(side_effect=CategoryNotFoundError("Not found"))
        )
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/categories/{uuid.uuid4()}",
                json={"name": "X"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "CATEGORY_NOT_FOUND"


# ── GET /categorization-rules ──────────────────────────────────────────────────

class TestGetRules:
    async def test_get_rules_returns_200(self):
        """Authenticated GET /categorization-rules → 200 with rule list."""
        settings = make_test_settings()
        rules = [_make_rule_response(priority=10), _make_rule_response(priority=0)]
        svc = _make_mock_service(list_rules=AsyncMock(return_value=rules))
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/categorization-rules", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2


# ── POST /categorization-rules ─────────────────────────────────────────────────

class TestPostRule:
    async def test_post_rule_returns_201(self):
        """Valid rule body → 201 with RuleResponse."""
        settings = make_test_settings()
        cat_id = uuid.uuid4()
        response_obj = _make_rule_response(pattern="zomato", match_type="contains", category_id=cat_id)
        svc = _make_mock_service(create_rule=AsyncMock(return_value=response_obj))
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/categorization-rules",
                json={"pattern": "zomato", "match_type": "contains", "category_id": str(cat_id)},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["pattern"] == "zomato"

    async def test_post_rule_invalid_regex_returns_422(self):
        """Creating a regex rule with invalid pattern → 422."""
        from elixir.shared.exceptions import InvalidRegexPatternError

        settings = make_test_settings()
        svc = _make_mock_service(
            create_rule=AsyncMock(side_effect=InvalidRegexPatternError("Invalid regex"))
        )
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/categorization-rules",
                json={"pattern": "[invalid(", "match_type": "regex", "category_id": str(uuid.uuid4())},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_REGEX_PATTERN"


# ── PATCH /categorization-rules/{id} ──────────────────────────────────────────

class TestPatchRule:
    async def test_patch_rule_returns_200(self):
        """Valid partial update of a rule → 200."""
        settings = make_test_settings()
        rule_id = uuid.uuid4()
        response_obj = _make_rule_response(id=rule_id, priority=10)
        svc = _make_mock_service(update_rule=AsyncMock(return_value=response_obj))
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                f"/categorization-rules/{rule_id}",
                json={"priority": 10},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == 10


# ── DELETE /categorization-rules/{id} ─────────────────────────────────────────

class TestDeleteRule:
    async def test_delete_rule_returns_204(self):
        """Successful deletion of a rule → 204."""
        settings = make_test_settings()
        rule_id = uuid.uuid4()
        svc = _make_mock_service(delete_rule=AsyncMock(return_value=None))
        app = _build_cat_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/categorization-rules/{rule_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204
