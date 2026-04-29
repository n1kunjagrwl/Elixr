from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ImportSourceType = Literal["csv_generic", "xlsx_generic", "splitwise_csv"]
ImportStatus = Literal[
    "uploaded", "awaiting_mapping", "processing", "completed", "failed"
]
MappingTarget = Literal[
    "date",
    "description",
    "debit_amount",
    "credit_amount",
    "amount",
    "balance",
    "category",
    "ignore",
]


class ColumnMapping(BaseModel):
    source_column: str
    mapped_to: MappingTarget


class ColumnMappingPreview(BaseModel):
    detected_columns: list[ColumnMapping]
    sample_rows: list[dict[str, str]] = []


class ColumnMappingConfirmRequest(BaseModel):
    mappings: list[ColumnMapping] = Field(min_length=1)


class ImportRowErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_index: int
    reason: str
    created_at: datetime | None = None


class ImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_type: str
    status: str
    total_rows: int | None = None
    imported_rows: int
    skipped_rows: int
    failed_rows: int
    created_at: datetime
    completed_at: datetime | None = None


class ImportJobDetailResponse(ImportJobResponse):
    original_filename: str | None = None
    temporal_workflow_id: str | None = None
    mappings: list[ColumnMapping] = []
    errors: list[ImportRowErrorResponse] = []


class ImportStartResponse(BaseModel):
    job_id: uuid.UUID
    stream_url: str


class SSEMappingEvent(BaseModel):
    event: str = "mapping_detected"
    data: ColumnMappingPreview
