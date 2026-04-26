from __future__ import annotations

import os
import uuid
from typing import Any
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.import_.repositories import ImportRepository
from elixir.domains.import_.schemas import (
    ColumnMapping,
    ImportJobDetailResponse,
    ImportJobResponse,
    ImportRowErrorResponse,
    ImportStartResponse,
    MappingTarget,
)
from elixir.shared.config import Settings
from elixir.shared.exceptions import (
    FileTooLargeError,
    ImportJobNotFoundError,
    ImportJobStateError,
    InvalidColumnMappingError,
    InvalidFileTypeError,
)

_MAX_FILE_SIZE = 50 * 1024 * 1024
_ALLOWED_FILE_TYPES = {"csv", "xlsx"}
_REQUIRED_MAPPING_TARGETS = {"date", "description"}
_AMOUNT_MAPPING_TARGETS = {"amount", "debit_amount", "credit_amount"}


class ImportService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self._db = db
        self._repo = ImportRepository(db)
        self._settings = settings

    async def upload_file(
        self,
        user_id: uuid.UUID,
        file_content: bytes,
        source_type: str,
        original_filename: str | None,
        storage_client: Any,
        temporal_client: Any,
    ) -> ImportStartResponse:
        if storage_client is None:
            from elixir.shared.exceptions import UnprocessableError
            raise UnprocessableError(
                "File storage is not configured. Import upload is currently unavailable."
            )

        extension = self._infer_extension(original_filename, source_type)
        if extension not in _ALLOWED_FILE_TYPES:
            raise InvalidFileTypeError(
                f"File type '{extension}' is not supported. Accepted: csv, xlsx."
            )
        if len(file_content) > _MAX_FILE_SIZE:
            raise FileTooLargeError("File size exceeds the 50 MB limit.")

        filename = f"{uuid.uuid4()}.{extension}"
        file_path = await storage_client.save(str(user_id), filename, file_content)
        job = await self._repo.create_job(
            user_id=user_id,
            file_path=file_path,
            original_filename=original_filename,
            source_type=source_type,
        )

        try:
            from elixir.domains.import_.workflows.import_processing import (
                ImportProcessingWorkflow,
            )

            wf_handle = await temporal_client.start_workflow(
                ImportProcessingWorkflow.run,
                args=[str(job.id), str(user_id), file_path, source_type],
                id=f"import-{job.id}",
                task_queue=self._settings.temporal_task_queue if self._settings else "elixir-main",
            )
            await self._repo.update_job(job, temporal_workflow_id=wf_handle.id)
        except Exception:
            pass

        await self._db.commit()
        return ImportStartResponse(job_id=job.id, stream_url=f"/import/{job.id}/stream")

    async def get_job_status(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ImportJobDetailResponse:
        job = await self._repo.get_job(user_id, job_id)
        if job is None:
            raise ImportJobNotFoundError(f"Import job {job_id} not found.")
        mappings = await self._repo.get_column_mappings(job.id)
        errors = await self._repo.get_row_errors(job.id)
        return ImportJobDetailResponse(
            id=job.id,
            user_id=job.user_id,
            source_type=job.source_type,
            status=job.status,
            total_rows=job.total_rows,
            imported_rows=job.imported_rows,
            skipped_rows=job.skipped_rows,
            failed_rows=job.failed_rows,
            created_at=job.created_at,
            completed_at=job.completed_at,
            original_filename=job.original_filename,
            temporal_workflow_id=job.temporal_workflow_id,
            mappings=[
                ColumnMapping(
                    source_column=mapping.source_column,
                    mapped_to=cast(MappingTarget, mapping.mapped_to),
                )
                for mapping in mappings
            ],
            errors=[
                ImportRowErrorResponse(
                    row_index=error.row_index,
                    reason=error.reason,
                    created_at=error.created_at,
                )
                for error in errors
            ],
        )

    async def list_jobs(self, user_id: uuid.UUID) -> list[ImportJobResponse]:
        jobs = await self._repo.list_jobs(user_id)
        return [ImportJobResponse.model_validate(job) for job in jobs]

    async def confirm_mapping(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        mappings: list[dict[str, Any]],
        temporal_client: Any,
    ) -> None:
        job = await self._repo.get_job(user_id, job_id)
        if job is None:
            raise ImportJobNotFoundError(f"Import job {job_id} not found.")
        if job.status not in {"uploaded", "awaiting_mapping"}:
            raise ImportJobStateError(
                f"Import job {job_id} is in state '{job.status}' and cannot accept mappings."
            )

        self._validate_mappings(mappings)
        await self._repo.replace_column_mappings(job.id, mappings)
        await self._repo.update_job(job, status="processing")

        try:
            if job.temporal_workflow_id:
                wf_handle = temporal_client.get_workflow_handle(job.temporal_workflow_id)
                await wf_handle.signal(
                    "ColumnMappingConfirmed",
                    [{"source_column": m["source_column"], "mapped_to": m["mapped_to"]} for m in mappings],
                )
        except Exception:
            pass

        await self._db.commit()

    async def delete_import(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> None:
        job = await self._repo.get_job(user_id, job_id)
        if job is None:
            raise ImportJobNotFoundError(f"Import job {job_id} not found.")
        if job.status not in {"completed", "failed"}:
            raise ImportJobStateError(
                f"Import job {job_id} is in state '{job.status}' and cannot be deleted."
            )
        await self._repo.delete_job(job.id)
        await self._db.commit()

    @staticmethod
    def _infer_extension(original_filename: str | None, source_type: str) -> str:
        if source_type == "xlsx_generic":
            return "xlsx"
        if source_type in {"csv_generic", "splitwise_csv"}:
            return "csv"
        if original_filename:
            return os.path.splitext(original_filename)[1].lstrip(".").lower()
        return ""

    @staticmethod
    def _validate_mappings(mappings: list[dict[str, Any]]) -> None:
        mapped_targets = {mapping["mapped_to"] for mapping in mappings}
        if not _REQUIRED_MAPPING_TARGETS.issubset(mapped_targets):
            raise InvalidColumnMappingError(
                "Mappings must include date and description."
            )
        if not mapped_targets.intersection(_AMOUNT_MAPPING_TARGETS):
            raise InvalidColumnMappingError(
                "Mappings must include amount, debit_amount, or credit_amount."
            )
