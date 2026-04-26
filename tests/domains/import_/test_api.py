"""
API-layer tests for the import_ domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The ImportService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient

from tests.conftest import SESSION_ID, USER_ID, make_test_settings
from elixir.shared.security import create_access_token


def _build_import_app(mock_service, settings=None):
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from elixir.domains.import_.api import router as import_router, get_import_service
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
    app.state.temporal_client = AsyncMock()
    app.state.storage = AsyncMock()

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    app.include_router(import_router, prefix="/import")

    app.dependency_overrides[get_import_service] = lambda: mock_service

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


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_job_response(**overrides) -> dict:
    defaults = dict(
        id=str(uuid.uuid4()),
        user_id=str(USER_ID),
        source_type="csv_generic",
        status="awaiting_mapping",
        total_rows=25,
        imported_rows=0,
        skipped_rows=0,
        failed_rows=0,
        created_at=_iso_now(),
        completed_at=None,
    )
    defaults.update(overrides)
    return defaults


def _make_job_detail_response(**overrides) -> dict:
    defaults = dict(
        **_make_job_response(),
        original_filename="test.csv",
        temporal_workflow_id="wf-123",
        mappings=[
            {"source_column": "Date", "mapped_to": "date"},
            {"source_column": "Narration", "mapped_to": "description"},
            {"source_column": "Amount", "mapped_to": "amount"},
        ],
        errors=[],
    )
    defaults.update(overrides)
    return defaults


class TestUploadEndpoint:
    async def test_upload_returns_201_with_job_id(self):
        settings = make_test_settings()
        job_id = uuid.uuid4()
        svc = _make_mock_service(
            upload_file=AsyncMock(
                return_value={"job_id": str(job_id), "stream_url": f"/import/{job_id}/stream"}
            )
        )
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/import/upload",
                files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
                data={"source_type": "csv_generic"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        assert "job_id" in resp.json()
        assert "stream_url" in resp.json()

    async def test_upload_invalid_source_type_returns_422(self):
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/import/upload",
                files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
                data={"source_type": "bad_type"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self):
        svc = _make_mock_service()
        app = _build_import_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/import/upload",
                files={"file": ("test.csv", b"a,b\n1,2", "text/csv")},
                data={"source_type": "csv_generic"},
            )

        assert resp.status_code == 401


class TestListJobs:
    async def test_list_jobs_returns_200(self):
        settings = make_test_settings()
        svc = _make_mock_service(
            list_jobs=AsyncMock(return_value=[_make_job_response(), _make_job_response()])
        )
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/import", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetJobStatus:
    async def test_get_job_status_returns_200(self):
        settings = make_test_settings()
        job_id = uuid.uuid4()
        svc = _make_mock_service(
            get_job_status=AsyncMock(return_value=_make_job_detail_response(id=str(job_id)))
        )
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/import/{job_id}", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        assert resp.json()["id"] == str(job_id)
        assert len(resp.json()["mappings"]) == 3


class TestConfirmMapping:
    async def test_confirm_mapping_returns_processing(self):
        settings = make_test_settings()
        job_id = uuid.uuid4()
        svc = _make_mock_service(confirm_mapping=AsyncMock(return_value=None))
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/import/{job_id}/confirm-mapping",
                json={
                    "mappings": [
                        {"source_column": "Date", "mapped_to": "date"},
                        {"source_column": "Narration", "mapped_to": "description"},
                        {"source_column": "Amount", "mapped_to": "amount"},
                    ]
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    async def test_confirm_mapping_invalid_target_returns_422(self):
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/import/{uuid.uuid4()}/confirm-mapping",
                json={
                    "mappings": [
                        {"source_column": "Date", "mapped_to": "date"},
                        {"source_column": "Narration", "mapped_to": "description"},
                        {"source_column": "Amount", "mapped_to": "signed_amount"},
                    ]
                },
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422


class TestStreamEndpoint:
    async def test_stream_endpoint_returns_sse(self):
        settings = make_test_settings()
        svc = _make_mock_service()
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/import/{uuid.uuid4()}/stream",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")


class TestDeleteJobEndpoint:
    async def test_delete_job_returns_204(self):
        """DELETE /import/{job_id} with a completed job returns 204 No Content."""
        settings = make_test_settings()
        svc = _make_mock_service(delete_import=AsyncMock(return_value=None))
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/import/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 204

    async def test_delete_active_job_returns_409(self):
        """DELETE /import/{job_id} with a processing job returns 409 Conflict."""
        from elixir.shared.exceptions import ImportJobStateError

        settings = make_test_settings()
        svc = _make_mock_service(
            delete_import=AsyncMock(side_effect=ImportJobStateError("Job is still active"))
        )
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/import/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 409
        assert resp.json()["error"] == "IMPORT_JOB_STATE_ERROR"

    async def test_delete_job_not_found_returns_404(self):
        """DELETE /import/{job_id} for a non-existent job returns 404."""
        from elixir.shared.exceptions import ImportJobNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            delete_import=AsyncMock(side_effect=ImportJobNotFoundError("Not found"))
        )
        app = _build_import_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(
                f"/import/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "IMPORT_JOB_NOT_FOUND"

    async def test_delete_job_unauthenticated_returns_401(self):
        """DELETE /import/{job_id} without auth returns 401."""
        svc = _make_mock_service()
        app = _build_import_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete(f"/import/{uuid.uuid4()}")

        assert resp.status_code == 401
