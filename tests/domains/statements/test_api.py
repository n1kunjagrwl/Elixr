"""
API-layer tests for the statements domain.

Uses httpx.AsyncClient against a minimal FastAPI app with:
- The StatementsService dependency overridden per test via dependency_overrides
- Auth middleware present; authenticated endpoints require a valid Bearer token
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import USER_ID, SESSION_ID, make_test_settings
from elixir.shared.security import create_access_token


# ── App builder ────────────────────────────────────────────────────────────────

def _build_statements_app(mock_service, settings=None):
    """
    Build a minimal FastAPI app that overrides the statements service dependency
    so HTTP-layer behaviour can be tested independently of service logic.
    """
    if settings is None:
        settings = make_test_settings()

    from contextlib import asynccontextmanager
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from elixir.domains.statements.api import router as statements_router, get_statements_service
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
    app.state.temporal_client = AsyncMock()
    app.state.storage = AsyncMock()

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    app.include_router(statements_router, prefix="/statements")

    app.dependency_overrides[get_statements_service] = lambda: mock_service

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


def _make_upload_start_response(job_id=None):
    from elixir.domains.statements.schemas import UploadStartResponse
    jid = job_id or uuid.uuid4()
    return UploadStartResponse(job_id=jid, stream_url=f"/statements/{jid}/stream")


def _make_upload_response(upload_id=None):
    from elixir.domains.statements.schemas import UploadResponse
    uid = upload_id or uuid.uuid4()
    return UploadResponse(
        id=uid,
        user_id=USER_ID,
        account_id=uuid.uuid4(),
        account_kind="bank",
        file_type="pdf",
        original_filename="test.pdf",
        status="uploaded",
        uploaded_at=datetime.now(timezone.utc),
    )


def _make_upload_status_response(upload_id=None, job_id=None):
    from elixir.domains.statements.schemas import UploadStatusResponse, ExtractionJobResponse
    uid = upload_id or uuid.uuid4()
    jid = job_id or uuid.uuid4()
    job = ExtractionJobResponse(
        id=jid,
        upload_id=uid,
        status="queued",
        classified_rows=0,
        created_at=datetime.now(timezone.utc),
    )
    return UploadStatusResponse(
        id=uid,
        user_id=USER_ID,
        account_id=uuid.uuid4(),
        account_kind="bank",
        file_type="pdf",
        original_filename="test.pdf",
        status="uploaded",
        uploaded_at=datetime.now(timezone.utc),
        job=job,
    )


def _make_row_response(row_id=None, job_id=None):
    from elixir.domains.statements.schemas import RawRowResponse
    return RawRowResponse(
        id=row_id or uuid.uuid4(),
        job_id=job_id or uuid.uuid4(),
        row_index=0,
        txn_date=date.today(),
        description="ATM WITHDRAWAL",
        debit_amount=Decimal("1000.00"),
        credit_amount=None,
        balance=Decimal("5000.00"),
        classification_status="pending",
        created_at=datetime.now(timezone.utc),
    )


# ── POST /statements/upload ────────────────────────────────────────────────────

class TestUploadEndpoint:
    async def test_upload_returns_201_with_job_id(self):
        """Valid PDF upload → 201 with job_id and stream_url."""
        settings = make_test_settings()
        job_id = uuid.uuid4()
        response_obj = _make_upload_start_response(job_id=job_id)
        svc = _make_mock_service(upload_statement=AsyncMock(return_value=response_obj))
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/statements/upload",
                files={"file": ("test.pdf", b"PDF content", "application/pdf")},
                data={"account_id": str(uuid.uuid4()), "account_kind": "bank", "file_type": "pdf"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "job_id" in data
        assert "stream_url" in data

    async def test_upload_invalid_type_returns_422(self):
        """Uploading with unsupported file_type → 422."""
        from elixir.shared.exceptions import InvalidFileTypeError

        settings = make_test_settings()
        svc = _make_mock_service(
            upload_statement=AsyncMock(side_effect=InvalidFileTypeError("Unsupported file type"))
        )
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/statements/upload",
                files={"file": ("test.xlsx", b"Excel content", "application/vnd.ms-excel")},
                data={"account_id": str(uuid.uuid4()), "account_kind": "bank", "file_type": "xlsx"},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 422

    async def test_unauthenticated_returns_401(self):
        """No auth header → 401."""
        svc = _make_mock_service()
        app = _build_statements_app(svc)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/statements/upload",
                files={"file": ("test.pdf", b"PDF content", "application/pdf")},
                data={"account_id": str(uuid.uuid4()), "account_kind": "bank", "file_type": "pdf"},
            )

        assert resp.status_code == 401


# ── GET /statements ────────────────────────────────────────────────────────────

class TestGetUploads:
    async def test_get_uploads_returns_200(self):
        """Authenticated GET /statements → 200 with list of uploads."""
        settings = make_test_settings()
        uploads = [_make_upload_response(), _make_upload_response()]
        svc = _make_mock_service(list_uploads=AsyncMock(return_value=uploads))
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/statements", headers=_make_auth_header(settings))

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 2


# ── GET /statements/{upload_id} ────────────────────────────────────────────────

class TestGetUploadStatus:
    async def test_get_upload_status_returns_200(self):
        """Authenticated GET /statements/{upload_id} → 200 with upload and job."""
        settings = make_test_settings()
        upload_id = uuid.uuid4()
        response_obj = _make_upload_status_response(upload_id=upload_id)
        svc = _make_mock_service(get_upload_status=AsyncMock(return_value=response_obj))
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/statements/{upload_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "job" in data

    async def test_get_upload_status_not_found_returns_404(self):
        """Service raises UploadNotFoundError → 404."""
        from elixir.shared.exceptions import UploadNotFoundError

        settings = make_test_settings()
        svc = _make_mock_service(
            get_upload_status=AsyncMock(side_effect=UploadNotFoundError("Not found"))
        )
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/statements/{uuid.uuid4()}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "UPLOAD_NOT_FOUND"


# ── POST /statements/{job_id}/rows/{row_id}/classify ──────────────────────────

class TestClassifyRow:
    async def test_classify_row_returns_200(self):
        """Valid classification request → 200."""
        settings = make_test_settings()
        job_id = uuid.uuid4()
        row_id = uuid.uuid4()
        svc = _make_mock_service(classify_row=AsyncMock(return_value=None))
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/statements/{job_id}/rows/{row_id}/classify",
                json={"category_id": str(uuid.uuid4())},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200

    async def test_classify_row_already_classified_returns_409(self):
        """Row already classified → 409."""
        from elixir.shared.exceptions import RowAlreadyClassifiedError

        settings = make_test_settings()
        job_id = uuid.uuid4()
        row_id = uuid.uuid4()
        svc = _make_mock_service(
            classify_row=AsyncMock(side_effect=RowAlreadyClassifiedError("Already classified"))
        )
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/statements/{job_id}/rows/{row_id}/classify",
                json={"category_id": str(uuid.uuid4())},
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 409
        assert resp.json()["error"] == "ROW_ALREADY_CLASSIFIED"


# ── GET /statements/{job_id}/rows ──────────────────────────────────────────────

class TestGetRows:
    async def test_get_rows_returns_200(self):
        """Authenticated GET /statements/{job_id}/rows → 200 with list of rows."""
        settings = make_test_settings()
        job_id = uuid.uuid4()
        rows = [_make_row_response(), _make_row_response()]
        svc = _make_mock_service(get_rows_for_resume=AsyncMock(return_value=rows))
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/statements/{job_id}/rows",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 2


# ── GET /statements/{job_id}/stream ───────────────────────────────────────────

class TestStreamEndpoint:
    async def test_stream_returns_200(self):
        """SSE stream endpoint returns 200 without error."""
        settings = make_test_settings()
        job_id = uuid.uuid4()
        svc = _make_mock_service()
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/statements/{job_id}/stream",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200


# ── GET /statements/jobs/{job_id} ─────────────────────────────────────────────

class TestGetJobResume:
    async def test_get_job_resume_returns_200(self):
        """GET /statements/jobs/{job_id} returns 200 with job + rows."""
        from elixir.domains.statements.schemas import (
            ExtractionJobResponse,
            JobResumeResponse,
            RawRowResponse,
        )
        settings = make_test_settings()
        job_id = uuid.uuid4()
        upload_id = uuid.uuid4()
        resume = JobResumeResponse(
            job=ExtractionJobResponse(
                id=job_id,
                upload_id=upload_id,
                status="awaiting_input",
                classified_rows=1,
                created_at=datetime.now(timezone.utc),
            ),
            rows=[_make_row_response(job_id=job_id)],
        )
        svc = _make_mock_service(get_job_resume=AsyncMock(return_value=resume))
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/statements/jobs/{job_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["job"]["id"] == str(job_id)
        assert body["job"]["status"] == "awaiting_input"
        assert len(body["rows"]) == 1

    async def test_get_job_resume_not_found_404(self):
        """GET /statements/jobs/{job_id} returns 404 when job not found."""
        from elixir.shared.exceptions import ExtractionJobNotFoundError

        settings = make_test_settings()
        job_id = uuid.uuid4()
        svc = _make_mock_service(
            get_job_resume=AsyncMock(side_effect=ExtractionJobNotFoundError("not found"))
        )
        app = _build_statements_app(svc, settings)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/statements/jobs/{job_id}",
                headers=_make_auth_header(settings),
            )

        assert resp.status_code == 404
        assert resp.json()["error"] == "EXTRACTION_JOB_NOT_FOUND"
