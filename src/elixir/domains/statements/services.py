import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.statements.events import StatementUploaded
from elixir.domains.statements.repositories import StatementsRepository
from elixir.domains.statements.schemas import (
    ClassifyRowRequest,
    ExtractionJobResponse,
    JobResumeResponse,
    RawRowResponse,
    UploadResponse,
    UploadStartResponse,
    UploadStatusResponse,
)
from elixir.shared.config import Settings
from elixir.shared.exceptions import (
    ExtractionJobNotFoundError,
    FileTooLargeError,
    InvalidFileTypeError,
    ItemAmountMismatchError,
    RowAlreadyClassifiedError,
    RowNotFoundError,
    UploadNotFoundError,
)

_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
_ALLOWED_FILE_TYPES = {"pdf", "csv"}
_ALREADY_CLASSIFIED_STATUSES = {"auto_classified", "user_classified"}


class StatementsService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._repo = StatementsRepository(db)
        self._settings = settings

    async def upload_statement(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        account_kind: str,
        file_content: bytes,
        file_type: str,
        original_filename: str | None,
        storage_client: Any,
        temporal_client: Any,
    ) -> UploadStartResponse:
        # Validate file type
        if file_type not in _ALLOWED_FILE_TYPES:
            raise InvalidFileTypeError(
                f"File type '{file_type}' is not supported. Accepted: pdf, csv."
            )

        # Validate file size
        if len(file_content) > _MAX_FILE_SIZE:
            raise FileTooLargeError(
                "File size exceeds the 20 MB limit."
            )

        # Save file to storage
        filename = f"{uuid.uuid4()}.{file_type}"
        file_path = await storage_client.save(
            str(user_id), filename, file_content
        )

        # Create upload row
        upload = await self._repo.create_upload(
            user_id=user_id,
            account_id=account_id,
            account_kind=account_kind,
            file_path=file_path,
            file_type=file_type,
            original_filename=original_filename,
        )

        # Create job row
        job = await self._repo.create_job(upload_id=upload.id)

        # Write outbox event (same transaction)
        event = StatementUploaded(
            upload_id=str(upload.id),
            user_id=str(user_id),
            account_id=str(account_id),
            file_type=file_type,
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())

        # Start Temporal workflow (best-effort — workflow can be started after commit)
        try:
            from elixir.domains.statements.workflows.statement_processing import (
                StatementProcessingWorkflow,
            )
            wf_handle = await temporal_client.start_workflow(
                StatementProcessingWorkflow.run,
                args=[str(job.id), str(upload.id)],
                id=f"statement-{job.id}",
                task_queue=self._settings.temporal_task_queue,
            )
            await self._repo.update_job_workflow_id(job, wf_handle.id)
        except Exception:
            # Temporal unavailable — job stays queued; a retry mechanism can restart it
            pass

        await self._db.commit()

        stream_url = f"/statements/{job.id}/stream"
        return UploadStartResponse(job_id=job.id, stream_url=stream_url)

    async def get_upload_status(
        self, user_id: uuid.UUID, upload_id: uuid.UUID
    ) -> UploadStatusResponse:
        upload = await self._repo.get_upload(user_id, upload_id)
        if upload is None:
            raise UploadNotFoundError(f"Upload {upload_id} not found.")

        job = await self._repo.get_job_for_upload(upload.id)
        job_response = ExtractionJobResponse.model_validate(job) if job else None

        return UploadStatusResponse(
            id=upload.id,
            user_id=upload.user_id,
            account_id=upload.account_id,
            account_kind=upload.account_kind,
            file_type=upload.file_type,
            original_filename=upload.original_filename,
            period_start=upload.period_start,
            period_end=upload.period_end,
            status=upload.status,
            uploaded_at=upload.uploaded_at,
            job=job_response,
        )

    async def list_uploads(self, user_id: uuid.UUID) -> list[UploadResponse]:
        uploads = await self._repo.list_uploads(user_id)
        return [UploadResponse.model_validate(u) for u in uploads]

    async def classify_row(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        row_id: uuid.UUID,
        data: ClassifyRowRequest,
        temporal_client: Any,
    ) -> None:
        # Verify job belongs to user
        job = await self._repo.get_job(user_id, job_id)
        if job is None:
            raise ExtractionJobNotFoundError(f"Extraction job {job_id} not found.")

        # Verify row belongs to job
        row = await self._repo.get_row(job_id, row_id)
        if row is None:
            raise RowNotFoundError(f"Row {row_id} not found in job {job_id}.")

        # Reject if already classified
        if row.classification_status in _ALREADY_CLASSIFIED_STATUSES:
            raise RowAlreadyClassifiedError(
                f"Row {row_id} is already classified as '{row.classification_status}'."
            )

        # Validate item amounts if provided
        if data.items:
            item_total = sum(item.amount for item in data.items)
            row_amount = row.debit_amount if row.debit_amount is not None else row.credit_amount
            if row_amount is None or item_total != row_amount:
                raise ItemAmountMismatchError(
                    f"Item amounts sum to {item_total} but row amount is {row_amount}."
                )

        # Update classification
        await self._repo.update_row_classification(
            row,
            final_category_id=data.category_id,
            classification_status="user_classified",
        )

        # Insert row items if provided
        if data.items:
            await self._repo.add_row_items(
                row_id=row_id,
                items=[{"label": item.label, "amount": item.amount} for item in data.items],
            )

        # Signal Temporal workflow
        try:
            if job.temporal_workflow_id:
                wf_handle = temporal_client.get_workflow_handle(
                    job.temporal_workflow_id
                )
                await wf_handle.signal("row_classified", row_id=str(row_id))
        except Exception:
            # Signal is best-effort
            pass

        await self._db.commit()

    async def get_rows_for_resume(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> list[RawRowResponse]:
        job = await self._repo.get_job(user_id, job_id)
        if job is None:
            raise ExtractionJobNotFoundError(f"Extraction job {job_id} not found.")

        rows = await self._repo.list_rows(job_id)
        return [RawRowResponse.model_validate(r) for r in rows]

    async def get_job_resume(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> JobResumeResponse:
        job = await self._repo.get_job(user_id, job_id)
        if job is None:
            raise ExtractionJobNotFoundError(f"Extraction job {job_id} not found.")

        rows = await self._repo.list_rows(job_id)
        return JobResumeResponse(
            job=ExtractionJobResponse.model_validate(job),
            rows=[RawRowResponse.model_validate(r) for r in rows],
        )
