"""
Service-layer tests for the statements domain.

All external dependencies (DB session, repository, storage, Temporal) are mocked.
No real database, network, or file system access.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_test_settings


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_service(mock_db):
    from elixir.domains.statements.services import StatementsService
    return StatementsService(db=mock_db, settings=make_test_settings())


ACCOUNT_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()
UPLOAD_ID = uuid.uuid4()
ROW_ID = uuid.uuid4()


def _make_upload(upload_id=None, user_id=None, status="uploaded"):
    u = MagicMock()
    u.id = upload_id or UPLOAD_ID
    u.user_id = user_id or USER_ID
    u.account_id = ACCOUNT_ID
    u.account_kind = "bank"
    u.file_path = "/uploads/test.pdf"
    u.file_type = "pdf"
    u.original_filename = "test.pdf"
    u.period_start = None
    u.period_end = None
    u.status = status
    u.uploaded_at = datetime.now(timezone.utc)
    return u


def _make_job(job_id=None, upload_id=None, status="queued", temporal_workflow_id=None):
    j = MagicMock()
    j.id = job_id or JOB_ID
    j.upload_id = upload_id or UPLOAD_ID
    j.temporal_workflow_id = temporal_workflow_id  # None → skip signal block in tests
    j.status = status
    j.total_rows = None
    j.classified_rows = 0
    j.error_message = None
    j.created_at = datetime.now(timezone.utc)
    j.completed_at = None
    return j


def _make_row(row_id=None, job_id=None, classification_status="pending"):
    r = MagicMock()
    r.id = row_id or ROW_ID
    r.job_id = job_id or JOB_ID
    r.row_index = 0
    r.date = date.today()
    r.description = "ATM WITHDRAWAL"
    r.debit_amount = Decimal("1000.00")
    r.credit_amount = None
    r.balance = Decimal("5000.00")
    r.classification_status = classification_status
    r.ai_suggested_category_id = None
    r.ai_confidence = None
    r.final_category_id = None
    r.transaction_id = None
    r.created_at = datetime.now(timezone.utc)
    return r


# ── upload_statement tests ─────────────────────────────────────────────────────

class TestUploadStatement:
    async def test_upload_statement_creates_upload_and_job_rows(self, mock_db):
        """Happy path: uploading a PDF creates upload + job rows and returns job_id + stream_url."""
        svc = _make_service(mock_db)

        upload = _make_upload()
        job = _make_job()
        mock_storage = AsyncMock()
        mock_storage.save = AsyncMock(return_value="/uploads/test.pdf")
        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock(return_value=MagicMock(id="wf-123"))

        with patch.object(svc._repo, "create_upload", new=AsyncMock(return_value=upload)), \
             patch.object(svc._repo, "create_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(return_value=None)):

            result = await svc.upload_statement(
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                account_kind="bank",
                file_content=b"PDF content",
                file_type="pdf",
                original_filename="test.pdf",
                storage_client=mock_storage,
                temporal_client=mock_temporal,
            )

        assert result.job_id == job.id
        assert "stream" in result.stream_url
        mock_db.commit.assert_called_once()

    async def test_upload_statement_invalid_file_type_raises_error(self, mock_db):
        """Uploading a file with unsupported type raises InvalidFileTypeError."""
        from elixir.shared.exceptions import InvalidFileTypeError

        svc = _make_service(mock_db)
        mock_storage = AsyncMock()
        mock_temporal = AsyncMock()

        with pytest.raises(InvalidFileTypeError):
            await svc.upload_statement(
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                account_kind="bank",
                file_content=b"some content",
                file_type="xlsx",
                original_filename="test.xlsx",
                storage_client=mock_storage,
                temporal_client=mock_temporal,
            )

    async def test_upload_statement_file_too_large_raises_error(self, mock_db):
        """Uploading a file exceeding 20 MB raises FileTooLargeError."""
        from elixir.shared.exceptions import FileTooLargeError

        svc = _make_service(mock_db)
        mock_storage = AsyncMock()
        mock_temporal = AsyncMock()

        large_content = b"x" * (20 * 1024 * 1024 + 1)

        with pytest.raises(FileTooLargeError):
            await svc.upload_statement(
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                account_kind="bank",
                file_content=large_content,
                file_type="pdf",
                original_filename="huge.pdf",
                storage_client=mock_storage,
                temporal_client=mock_temporal,
            )

    async def test_upload_statement_writes_outbox_event(self, mock_db):
        """Uploading a statement writes a StatementUploaded event to the outbox."""
        svc = _make_service(mock_db)

        upload = _make_upload()
        job = _make_job()
        outbox_events: list = []
        mock_storage = AsyncMock()
        mock_storage.save = AsyncMock(return_value="/uploads/test.pdf")
        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock(return_value=MagicMock(id="wf-123"))

        with patch.object(svc._repo, "create_upload", new=AsyncMock(return_value=upload)), \
             patch.object(svc._repo, "create_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "add_outbox_event",
                         new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p)))):

            await svc.upload_statement(
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                account_kind="bank",
                file_content=b"PDF content",
                file_type="pdf",
                original_filename="test.pdf",
                storage_client=mock_storage,
                temporal_client=mock_temporal,
            )

        assert len(outbox_events) == 1
        event_type, payload = outbox_events[0]
        assert event_type == "statements.StatementUploaded"
        assert payload["user_id"] == str(USER_ID)
        assert payload["account_id"] == str(ACCOUNT_ID)
        assert payload["file_type"] == "pdf"


# ── get_upload_status tests ────────────────────────────────────────────────────

class TestGetUploadStatus:
    async def test_get_upload_status_returns_upload_and_job(self, mock_db):
        """Happy path: returns UploadStatusResponse with upload and job data."""
        svc = _make_service(mock_db)

        upload = _make_upload()
        job = _make_job()

        with patch.object(svc._repo, "get_upload", new=AsyncMock(return_value=upload)), \
             patch.object(svc._repo, "get_job_for_upload", new=AsyncMock(return_value=job)):

            result = await svc.get_upload_status(USER_ID, UPLOAD_ID)

        assert result.id == upload.id
        assert result.status == "uploaded"
        assert result.job is not None
        assert result.job.id == job.id

    async def test_get_upload_status_not_found_raises_404(self, mock_db):
        """When upload is not found, UploadNotFoundError is raised."""
        from elixir.shared.exceptions import UploadNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_upload", new=AsyncMock(return_value=None)):
            with pytest.raises(UploadNotFoundError):
                await svc.get_upload_status(USER_ID, uuid.uuid4())


# ── list_uploads tests ─────────────────────────────────────────────────────────

class TestListUploads:
    async def test_list_uploads_returns_user_uploads(self, mock_db):
        """list_uploads returns all uploads belonging to the requesting user."""
        svc = _make_service(mock_db)

        uploads = [_make_upload(), _make_upload(upload_id=uuid.uuid4())]

        with patch.object(svc._repo, "list_uploads", new=AsyncMock(return_value=uploads)):
            results = await svc.list_uploads(USER_ID)

        assert len(results) == 2
        for r in results:
            assert r.user_id == USER_ID


# ── classify_row tests ─────────────────────────────────────────────────────────

class TestClassifyRow:
    async def test_classify_row_updates_classification_status(self, mock_db):
        """Happy path: row is pending → user classifies it → status becomes user_classified."""
        svc = _make_service(mock_db)

        job = _make_job()
        row = _make_row(classification_status="pending")
        mock_temporal = AsyncMock()

        from elixir.domains.statements.schemas import ClassifyRowRequest

        data = ClassifyRowRequest(category_id=uuid.uuid4())

        mock_update = AsyncMock(return_value=None)
        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "get_row", new=AsyncMock(return_value=row)), \
             patch.object(svc._repo, "update_row_classification", new=mock_update), \
             patch.object(svc._repo, "add_row_items", new=AsyncMock(return_value=None)):

            await svc.classify_row(
                user_id=USER_ID,
                job_id=JOB_ID,
                row_id=ROW_ID,
                data=data,
                temporal_client=mock_temporal,
            )

        mock_update.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_classify_row_wrong_user_raises_404(self, mock_db):
        """When job belongs to another user, RowNotFoundError is raised."""
        from elixir.shared.exceptions import ExtractionJobNotFoundError

        svc = _make_service(mock_db)
        mock_temporal = AsyncMock()

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=None)):
            with pytest.raises(ExtractionJobNotFoundError):
                from elixir.domains.statements.schemas import ClassifyRowRequest
                await svc.classify_row(
                    user_id=USER_ID,
                    job_id=JOB_ID,
                    row_id=ROW_ID,
                    data=ClassifyRowRequest(category_id=uuid.uuid4()),
                    temporal_client=mock_temporal,
                )

    async def test_classify_row_already_classified_raises_409(self, mock_db):
        """Attempting to classify an already-classified row raises RowAlreadyClassifiedError."""
        from elixir.shared.exceptions import RowAlreadyClassifiedError

        svc = _make_service(mock_db)

        job = _make_job()
        row = _make_row(classification_status="auto_classified")
        mock_temporal = AsyncMock()

        from elixir.domains.statements.schemas import ClassifyRowRequest

        data = ClassifyRowRequest(category_id=uuid.uuid4())

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "get_row", new=AsyncMock(return_value=row)):

            with pytest.raises(RowAlreadyClassifiedError):
                await svc.classify_row(
                    user_id=USER_ID,
                    job_id=JOB_ID,
                    row_id=ROW_ID,
                    data=data,
                    temporal_client=mock_temporal,
                )

    async def test_classify_row_with_items_validates_sum(self, mock_db):
        """When items are provided and sum equals debit_amount, succeeds."""
        svc = _make_service(mock_db)

        job = _make_job()
        row = _make_row(classification_status="pending")
        row.debit_amount = Decimal("1000.00")
        row.credit_amount = None
        mock_temporal = AsyncMock()

        from elixir.domains.statements.schemas import ClassifyRowRequest, RowItemInput

        data = ClassifyRowRequest(
            category_id=uuid.uuid4(),
            items=[
                RowItemInput(label="Food", amount=Decimal("600.00")),
                RowItemInput(label="Transport", amount=Decimal("400.00")),
            ],
        )

        mock_add_items = AsyncMock(return_value=None)
        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "get_row", new=AsyncMock(return_value=row)), \
             patch.object(svc._repo, "update_row_classification", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "add_row_items", new=mock_add_items):

            await svc.classify_row(
                user_id=USER_ID,
                job_id=JOB_ID,
                row_id=ROW_ID,
                data=data,
                temporal_client=mock_temporal,
            )

        mock_add_items.assert_called_once()

    async def test_classify_row_items_wrong_sum_raises_422(self, mock_db):
        """When item amounts don't sum to debit or credit amount, ItemAmountMismatchError is raised."""
        from elixir.shared.exceptions import ItemAmountMismatchError

        svc = _make_service(mock_db)

        job = _make_job()
        row = _make_row(classification_status="pending")
        row.debit_amount = Decimal("1000.00")
        row.credit_amount = None
        mock_temporal = AsyncMock()

        from elixir.domains.statements.schemas import ClassifyRowRequest, RowItemInput

        data = ClassifyRowRequest(
            category_id=uuid.uuid4(),
            items=[
                RowItemInput(label="Food", amount=Decimal("300.00")),
                # total is 300 but row is 1000
            ],
        )

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "get_row", new=AsyncMock(return_value=row)):

            with pytest.raises(ItemAmountMismatchError):
                await svc.classify_row(
                    user_id=USER_ID,
                    job_id=JOB_ID,
                    row_id=ROW_ID,
                    data=data,
                    temporal_client=mock_temporal,
                )


# ── get_rows_for_resume tests ──────────────────────────────────────────────────

class TestGetRowsForResume:
    async def test_get_rows_for_resume_returns_rows(self, mock_db):
        """get_rows_for_resume returns all raw extracted rows for a job."""
        svc = _make_service(mock_db)

        job = _make_job()
        rows = [_make_row(), _make_row(row_id=uuid.uuid4())]

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "list_rows", new=AsyncMock(return_value=rows)):

            result = await svc.get_rows_for_resume(USER_ID, JOB_ID)

        assert len(result) == 2


# ── get_job_resume tests ───────────────────────────────────────────────────────

class TestGetJobResume:
    async def test_get_job_resume_returns_job_and_rows(self, mock_db):
        """get_job_resume returns job metadata and all rows combined."""
        svc = _make_service(mock_db)

        job = _make_job(status="awaiting_input")
        job.total_rows = 3
        job.classified_rows = 1
        rows = [_make_row(), _make_row(row_id=uuid.uuid4(), classification_status="user_classified")]

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "list_rows", new=AsyncMock(return_value=rows)):

            result = await svc.get_job_resume(USER_ID, JOB_ID)

        assert result.job.id == job.id
        assert result.job.status == "awaiting_input"
        assert len(result.rows) == 2

    async def test_get_job_resume_not_found_raises(self, mock_db):
        """When job is not found for user, ExtractionJobNotFoundError is raised."""
        from elixir.shared.exceptions import ExtractionJobNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=None)):
            with pytest.raises(ExtractionJobNotFoundError):
                await svc.get_job_resume(USER_ID, uuid.uuid4())
