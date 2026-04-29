import uuid
import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Shared sub-schemas ─────────────────────────────────────────────────────────


class RowItemInput(BaseModel):
    """A sub-item for split-row classification."""

    label: Optional[str] = None
    amount: Decimal


class ExtractionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    upload_id: uuid.UUID
    temporal_workflow_id: Optional[str] = None
    status: str
    total_rows: Optional[int] = None
    classified_rows: int = 0
    error_message: Optional[str] = None
    created_at: dt.datetime
    completed_at: Optional[dt.datetime] = None


# ── Upload schemas ─────────────────────────────────────────────────────────────


class UploadStartResponse(BaseModel):
    """Returned by POST /statements/upload."""

    job_id: uuid.UUID
    stream_url: str


class UploadResponse(BaseModel):
    """Lightweight upload listing entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    account_kind: str
    file_type: str
    original_filename: Optional[str] = None
    period_start: Optional[dt.date] = None
    period_end: Optional[dt.date] = None
    status: str
    uploaded_at: dt.datetime


class UploadStatusResponse(UploadResponse):
    """Full upload detail with embedded job."""

    job: Optional[ExtractionJobResponse] = None


# ── Row schemas ────────────────────────────────────────────────────────────────


class RawRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    job_id: uuid.UUID
    row_index: int
    # 'date' is a reserved Python name; expose as txn_date with validation_alias
    txn_date: Optional[dt.date] = Field(default=None, validation_alias="date")
    description: Optional[str] = None
    debit_amount: Optional[Decimal] = None
    credit_amount: Optional[Decimal] = None
    balance: Optional[Decimal] = None
    classification_status: str
    ai_suggested_category_id: Optional[uuid.UUID] = None
    ai_confidence: Optional[float] = None
    final_category_id: Optional[uuid.UUID] = None
    transaction_id: Optional[uuid.UUID] = None
    created_at: dt.datetime


# ── Resume schemas ────────────────────────────────────────────────────────────


class JobResumeResponse(BaseModel):
    """Returned by GET /statements/jobs/{job_id} — job status + all rows."""

    job: ExtractionJobResponse
    rows: list[RawRowResponse]


# ── Classification schemas ─────────────────────────────────────────────────────


class ClassifyRowRequest(BaseModel):
    """Body for POST /statements/{job_id}/rows/{row_id}/classify."""

    category_id: uuid.UUID
    items: Optional[list[RowItemInput]] = None
