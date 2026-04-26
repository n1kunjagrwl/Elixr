"""
Service-layer tests for the import_ domain.

All external dependencies (DB session, repository, storage, Temporal) are mocked.
No real database, network, or file system access.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_test_settings


def _make_service(mock_db):
    from elixir.domains.import_.services import ImportService

    return ImportService(db=mock_db, settings=make_test_settings())


JOB_ID = uuid.uuid4()


def _make_job(
    job_id=None,
    user_id=None,
    source_type="csv_generic",
    status="uploaded",
    temporal_workflow_id=None,
):
    job = MagicMock()
    job.id = job_id or JOB_ID
    job.user_id = user_id or USER_ID
    job.file_path = "/imports/test.csv"
    job.original_filename = "test.csv"
    job.source_type = source_type
    job.temporal_workflow_id = temporal_workflow_id
    job.status = status
    job.total_rows = None
    job.imported_rows = 0
    job.skipped_rows = 0
    job.failed_rows = 0
    job.created_at = datetime.now(timezone.utc)
    job.completed_at = None
    return job


def _make_mapping(source_column="Date", mapped_to="date"):
    mapping = MagicMock()
    mapping.source_column = source_column
    mapping.mapped_to = mapped_to
    mapping.created_at = datetime.now(timezone.utc)
    return mapping


def _make_row_error(row_index=2, reason="invalid date"):
    error = MagicMock()
    error.row_index = row_index
    error.reason = reason
    error.created_at = datetime.now(timezone.utc)
    return error


class TestUploadFile:
    async def test_upload_file_creates_job_and_returns_stream_url(self, mock_db):
        svc = _make_service(mock_db)
        job = _make_job()
        mock_storage = AsyncMock()
        mock_storage.save = AsyncMock(return_value="/imports/test.csv")
        mock_temporal = AsyncMock()
        mock_temporal.start_workflow = AsyncMock(return_value=MagicMock(id="wf-123"))

        with patch.object(
            svc._repo,
            "create_job",
            new=AsyncMock(return_value=job),
        ), patch.object(
            svc._repo,
            "update_job",
            new=AsyncMock(return_value=None),
        ):
            result = await svc.upload_file(
                user_id=USER_ID,
                file_content=b"Date,Description,Amount\n",
                source_type="csv_generic",
                original_filename="test.csv",
                storage_client=mock_storage,
                temporal_client=mock_temporal,
            )

        assert result.job_id == job.id
        assert result.stream_url == f"/import/{job.id}/stream"
        mock_db.commit.assert_called_once()

    async def test_upload_file_invalid_file_type_raises_error(self, mock_db):
        from elixir.shared.exceptions import InvalidFileTypeError

        svc = _make_service(mock_db)

        with pytest.raises(InvalidFileTypeError):
            await svc.upload_file(
                user_id=USER_ID,
                file_content=b"content",
                source_type="unknown",
                original_filename="test.unknown",
                storage_client=AsyncMock(),
                temporal_client=AsyncMock(),
            )

    async def test_upload_file_too_large_raises_error(self, mock_db):
        from elixir.shared.exceptions import FileTooLargeError

        svc = _make_service(mock_db)

        with pytest.raises(FileTooLargeError):
            await svc.upload_file(
                user_id=USER_ID,
                file_content=b"x" * (50 * 1024 * 1024 + 1),
                source_type="csv_generic",
                original_filename="huge.csv",
                storage_client=AsyncMock(),
                temporal_client=AsyncMock(),
            )


class TestGetJobStatus:
    async def test_get_job_status_returns_job_with_mappings_and_errors(self, mock_db):
        svc = _make_service(mock_db)
        job = _make_job(status="processing")
        mappings = [_make_mapping()]
        errors = [_make_row_error()]

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "get_column_mappings", new=AsyncMock(return_value=mappings)), \
             patch.object(svc._repo, "get_row_errors", new=AsyncMock(return_value=errors)):
            result = await svc.get_job_status(USER_ID, job.id)

        assert result.id == job.id
        assert result.status == "processing"
        assert len(result.mappings) == 1
        assert result.mappings[0].source_column == "Date"
        assert len(result.errors) == 1
        assert result.errors[0].reason == "invalid date"

    async def test_get_job_status_not_found_raises_404(self, mock_db):
        from elixir.shared.exceptions import ImportJobNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=None)):
            with pytest.raises(ImportJobNotFoundError):
                await svc.get_job_status(USER_ID, uuid.uuid4())


class TestListJobs:
    async def test_list_jobs_returns_user_jobs(self, mock_db):
        svc = _make_service(mock_db)
        jobs = [_make_job(), _make_job(job_id=uuid.uuid4(), status="completed")]

        with patch.object(svc._repo, "list_jobs", new=AsyncMock(return_value=jobs)):
            result = await svc.list_jobs(USER_ID)

        assert len(result) == 2
        assert result[0].user_id == USER_ID


class TestConfirmMapping:
    async def test_confirm_mapping_replaces_rows_updates_status_and_signals_workflow(self, mock_db):
        svc = _make_service(mock_db)
        job = _make_job(status="awaiting_mapping", temporal_workflow_id="wf-123")
        mock_temporal = MagicMock()
        handle = AsyncMock()
        mock_temporal.get_workflow_handle = MagicMock(return_value=handle)

        mappings = [
            {"source_column": "Date", "mapped_to": "date"},
            {"source_column": "Narration", "mapped_to": "description"},
            {"source_column": "Amount", "mapped_to": "amount"},
        ]

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "replace_column_mappings", new=AsyncMock(return_value=[])) as mock_replace, \
             patch.object(svc._repo, "update_job", new=AsyncMock(return_value=None)) as mock_update:
            await svc.confirm_mapping(USER_ID, job.id, mappings, mock_temporal)

        mock_replace.assert_awaited_once_with(job.id, mappings)
        mock_update.assert_awaited_once()
        handle.signal.assert_awaited_once()
        mock_db.commit.assert_called_once()

    async def test_confirm_mapping_invalid_mapping_raises_422(self, mock_db):
        from elixir.shared.exceptions import InvalidColumnMappingError

        svc = _make_service(mock_db)
        job = _make_job(status="awaiting_mapping")

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)):
            with pytest.raises(InvalidColumnMappingError):
                await svc.confirm_mapping(
                    USER_ID,
                    job.id,
                    [
                        {"source_column": "Date", "mapped_to": "date"},
                        {"source_column": "Amount", "mapped_to": "amount"},
                    ],
                    AsyncMock(),
                )

        mock_db.commit.assert_not_called()

    async def test_confirm_mapping_job_not_found_raises_404(self, mock_db):
        from elixir.shared.exceptions import ImportJobNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=None)):
            with pytest.raises(ImportJobNotFoundError):
                await svc.confirm_mapping(USER_ID, uuid.uuid4(), [], AsyncMock())

    async def test_confirm_mapping_wrong_job_state_raises_conflict(self, mock_db):
        from elixir.shared.exceptions import ImportJobStateError

        svc = _make_service(mock_db)
        job = _make_job(status="completed")

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)):
            with pytest.raises(ImportJobStateError):
                await svc.confirm_mapping(
                    USER_ID,
                    job.id,
                    [
                        {"source_column": "Date", "mapped_to": "date"},
                        {"source_column": "Narration", "mapped_to": "description"},
                        {"source_column": "Amount", "mapped_to": "amount"},
                    ],
                    AsyncMock(),
                )


class TestDeleteImport:
    async def test_delete_import_removes_completed_job(self, mock_db):
        """Deleting a completed job calls repo.delete_job and commits."""
        svc = _make_service(mock_db)
        job = _make_job(status="completed")

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "delete_job", new=AsyncMock(return_value=None)) as mock_delete:
            await svc.delete_import(USER_ID, job.id)

        mock_delete.assert_awaited_once_with(job.id)
        mock_db.commit.assert_called_once()

    async def test_delete_import_removes_failed_job(self, mock_db):
        """Deleting a failed job is also allowed."""
        svc = _make_service(mock_db)
        job = _make_job(status="failed")

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)), \
             patch.object(svc._repo, "delete_job", new=AsyncMock(return_value=None)) as mock_delete:
            await svc.delete_import(USER_ID, job.id)

        mock_delete.assert_awaited_once_with(job.id)

    async def test_delete_import_active_job_raises_409(self, mock_db):
        """Deleting a job that is still processing raises ImportJobStateError (409)."""
        from elixir.shared.exceptions import ImportJobStateError

        svc = _make_service(mock_db)
        job = _make_job(status="processing")

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)):
            with pytest.raises(ImportJobStateError):
                await svc.delete_import(USER_ID, job.id)

        mock_db.commit.assert_not_called()

    async def test_delete_import_uploaded_job_raises_409(self, mock_db):
        """Deleting a job in 'uploaded' state (still active) raises ImportJobStateError (409)."""
        from elixir.shared.exceptions import ImportJobStateError

        svc = _make_service(mock_db)
        job = _make_job(status="uploaded")

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=job)):
            with pytest.raises(ImportJobStateError):
                await svc.delete_import(USER_ID, job.id)

        mock_db.commit.assert_not_called()

    async def test_delete_import_not_found_raises_404(self, mock_db):
        """Deleting a non-existent job raises ImportJobNotFoundError (404)."""
        from elixir.shared.exceptions import ImportJobNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_job", new=AsyncMock(return_value=None)):
            with pytest.raises(ImportJobNotFoundError):
                await svc.delete_import(USER_ID, uuid.uuid4())

        mock_db.commit.assert_not_called()
