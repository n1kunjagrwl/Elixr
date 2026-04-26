import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.import_.models import (
    ImportColumnMapping,
    ImportJob,
    ImportOutbox,
    ImportRowError,
)


class ImportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_job(
        self,
        user_id: uuid.UUID,
        file_path: str,
        original_filename: str | None,
        source_type: str,
    ) -> ImportJob:
        job = ImportJob(
            user_id=user_id,
            file_path=file_path,
            original_filename=original_filename,
            source_type=source_type,
        )
        self._db.add(job)
        await self._db.flush()
        return job

    async def get_job(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> ImportJob | None:
        result = await self._db.execute(
            select(ImportJob).where(
                ImportJob.id == job_id,
                ImportJob.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_job(self, job: ImportJob, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(job, key, value)
        if "completed_at" not in fields and fields.get("status") in {"completed", "failed"}:
            job.completed_at = datetime.now(timezone.utc)

    async def create_column_mappings(
        self,
        job_id: uuid.UUID,
        mappings: list[dict[str, Any]],
    ) -> list[ImportColumnMapping]:
        created: list[ImportColumnMapping] = []
        for mapping in mappings:
            row = ImportColumnMapping(
                job_id=job_id,
                source_column=mapping["source_column"],
                mapped_to=mapping["mapped_to"],
            )
            self._db.add(row)
            created.append(row)
        await self._db.flush()
        return created

    async def replace_column_mappings(
        self,
        job_id: uuid.UUID,
        mappings: list[dict[str, Any]],
    ) -> list[ImportColumnMapping]:
        await self._db.execute(
            delete(ImportColumnMapping).where(ImportColumnMapping.job_id == job_id)
        )
        await self._db.flush()
        return await self.create_column_mappings(job_id, mappings)

    async def get_column_mappings(
        self,
        job_id: uuid.UUID,
    ) -> list[ImportColumnMapping]:
        result = await self._db.execute(
            select(ImportColumnMapping)
            .where(ImportColumnMapping.job_id == job_id)
            .order_by(ImportColumnMapping.created_at, ImportColumnMapping.id)
        )
        return list(result.scalars().all())

    async def create_row_errors(
        self,
        job_id: uuid.UUID,
        errors: list[dict[str, Any]],
    ) -> list[ImportRowError]:
        created: list[ImportRowError] = []
        for error in errors:
            row = ImportRowError(
                job_id=job_id,
                row_index=error["row_index"],
                reason=error["reason"],
            )
            self._db.add(row)
            created.append(row)
        await self._db.flush()
        return created

    async def get_row_errors(
        self,
        job_id: uuid.UUID,
    ) -> list[ImportRowError]:
        result = await self._db.execute(
            select(ImportRowError)
            .where(ImportRowError.job_id == job_id)
            .order_by(ImportRowError.row_index.asc(), ImportRowError.id.asc())
        )
        return list(result.scalars().all())

    async def list_jobs(self, user_id: uuid.UUID) -> list[ImportJob]:
        result = await self._db.execute(
            select(ImportJob)
            .where(ImportJob.user_id == user_id)
            .order_by(ImportJob.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_job(self, job_id: uuid.UUID) -> None:
        await self._db.execute(
            delete(ImportJob).where(ImportJob.id == job_id)
        )

    async def add_outbox_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> None:
        row = ImportOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
