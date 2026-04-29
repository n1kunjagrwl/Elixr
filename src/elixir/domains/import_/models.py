import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, TimestampMixin


class ImportJob(Base, IDMixin, TimestampMixin):
    __tablename__ = "import_jobs"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('csv_generic','xlsx_generic','splitwise_csv')",
            name="ck_import_jobs_source_type",
        ),
        CheckConstraint(
            "status IN ('uploaded','awaiting_mapping','processing','completed','failed')",
            name="ck_import_jobs_status",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    temporal_workflow_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ImportColumnMapping(Base, IDMixin, TimestampMixin):
    __tablename__ = "import_column_mappings"
    __table_args__ = (
        CheckConstraint(
            "mapped_to IN ('date','description','debit_amount','credit_amount','amount','balance','category','ignore')",
            name="ck_import_column_mappings_mapped_to",
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_column: Mapped[str] = mapped_column(Text, nullable=False)
    mapped_to: Mapped[str] = mapped_column(String(30), nullable=False)


class ImportRowError(Base, IDMixin, TimestampMixin):
    __tablename__ = "import_row_errors"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class ImportOutbox(Base, IDMixin, TimestampMixin):
    __tablename__ = "import_outbox"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
