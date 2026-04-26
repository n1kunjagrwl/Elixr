import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, TimestampMixin


class StatementUpload(Base, IDMixin):
    """
    Represents a single file upload from a user.
    Uses uploaded_at instead of created_at — do NOT use TimestampMixin.
    """

    __tablename__ = "statement_uploads"
    __table_args__ = (
        CheckConstraint(
            "account_kind IN ('bank','credit_card')",
            name="ck_statement_uploads_account_kind",
        ),
        CheckConstraint(
            "file_type IN ('pdf','csv')",
            name="ck_statement_uploads_file_type",
        ),
        CheckConstraint(
            "status IN ('uploaded','processing','completed','partial','failed')",
            name="ck_statement_uploads_status",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    account_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded"
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExtractionJob(Base, IDMixin, TimestampMixin):
    """Tracks the Temporal workflow that processes a StatementUpload."""

    __tablename__ = "extraction_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','parsing','classifying','awaiting_input','completed','partial','failed')",
            name="ck_extraction_jobs_status",
        ),
    )

    upload_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("statement_uploads.id"),
        nullable=False,
        index=True,
    )
    temporal_workflow_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="queued"
    )
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classified_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RawExtractedRow(Base, IDMixin, TimestampMixin):
    """One row parsed from a bank/credit card statement."""

    __tablename__ = "raw_extracted_rows"
    __table_args__ = (
        CheckConstraint(
            "classification_status IN ('pending','auto_classified','user_classified','skipped')",
            name="ck_raw_extracted_rows_classification_status",
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("extraction_jobs.id"),
        nullable=False,
        index=True,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    credit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    classification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )
    ai_suggested_category_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_category_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )


class RawRowItem(Base, IDMixin, TimestampMixin):
    """A sub-item (split) within a RawExtractedRow."""

    __tablename__ = "raw_row_items"

    row_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("raw_extracted_rows.id"),
        nullable=False,
        index=True,
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)


class StatementsOutbox(Base, IDMixin, TimestampMixin):
    """Outbox table for statements domain events."""

    __tablename__ = "statements_outbox"

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
