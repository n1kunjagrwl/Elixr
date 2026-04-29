import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.statements.models import (
    ExtractionJob,
    RawExtractedRow,
    RawRowItem,
    StatementsOutbox,
    StatementUpload,
)


class StatementsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── StatementUpload ────────────────────────────────────────────────────────

    async def create_upload(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        account_kind: str,
        file_path: str,
        file_type: str,
        original_filename: str | None = None,
    ) -> StatementUpload:
        upload = StatementUpload(
            user_id=user_id,
            account_id=account_id,
            account_kind=account_kind,
            file_path=file_path,
            file_type=file_type,
            original_filename=original_filename,
        )
        self._db.add(upload)
        await self._db.flush()
        return upload

    async def get_upload(
        self, user_id: uuid.UUID, upload_id: uuid.UUID
    ) -> StatementUpload | None:
        result = await self._db.execute(
            select(StatementUpload).where(
                StatementUpload.id == upload_id,
                StatementUpload.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_uploads(self, user_id: uuid.UUID) -> list[StatementUpload]:
        result = await self._db.execute(
            select(StatementUpload)
            .where(StatementUpload.user_id == user_id)
            .order_by(StatementUpload.uploaded_at.desc())
        )
        return list(result.scalars().all())

    # ── ExtractionJob ──────────────────────────────────────────────────────────

    async def create_job(
        self,
        upload_id: uuid.UUID,
        temporal_workflow_id: str | None = None,
    ) -> ExtractionJob:
        job = ExtractionJob(
            upload_id=upload_id,
            temporal_workflow_id=temporal_workflow_id,
        )
        self._db.add(job)
        await self._db.flush()
        return job

    async def get_job(
        self, user_id: uuid.UUID, job_id: uuid.UUID
    ) -> ExtractionJob | None:
        """
        Fetch a job ensuring it belongs to a user by joining through StatementUpload.
        """
        result = await self._db.execute(
            select(ExtractionJob)
            .join(StatementUpload, ExtractionJob.upload_id == StatementUpload.id)
            .where(
                ExtractionJob.id == job_id,
                StatementUpload.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_job_for_upload(self, upload_id: uuid.UUID) -> ExtractionJob | None:
        result = await self._db.execute(
            select(ExtractionJob)
            .where(ExtractionJob.upload_id == upload_id)
            .order_by(ExtractionJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_job_workflow_id(
        self, job: ExtractionJob, workflow_id: str
    ) -> None:
        job.temporal_workflow_id = workflow_id

    # ── RawExtractedRow ────────────────────────────────────────────────────────

    async def get_row(
        self, job_id: uuid.UUID, row_id: uuid.UUID
    ) -> RawExtractedRow | None:
        result = await self._db.execute(
            select(RawExtractedRow).where(
                RawExtractedRow.id == row_id,
                RawExtractedRow.job_id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_rows(self, job_id: uuid.UUID) -> list[RawExtractedRow]:
        result = await self._db.execute(
            select(RawExtractedRow)
            .where(RawExtractedRow.job_id == job_id)
            .order_by(RawExtractedRow.row_index)
        )
        return list(result.scalars().all())

    async def update_row_classification(
        self,
        row: RawExtractedRow,
        final_category_id: uuid.UUID,
        classification_status: str = "user_classified",
    ) -> None:
        row.final_category_id = final_category_id
        row.classification_status = classification_status

    # ── RawRowItem ─────────────────────────────────────────────────────────────

    async def add_row_items(
        self,
        row_id: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> None:
        for item in items:
            row_item = RawRowItem(
                row_id=row_id,
                label=item.get("label"),
                amount=item["amount"],
            )
            self._db.add(row_item)

    # ── Outbox ─────────────────────────────────────────────────────────────────

    async def add_outbox_event(self, event_type: str, payload: dict[str, Any]) -> None:
        row = StatementsOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
