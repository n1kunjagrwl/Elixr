from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EarningType = Literal[
    "salary",
    "freelance",
    "rental",
    "dividend",
    "interest",
    "business",
    "other",
]
ClassificationType = Literal["income", "peer_repayment", "ignore"]


class EarningSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: EarningType


class EarningSourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: EarningType | None = None
    is_active: bool | None = None


class EarningSourceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    type: str
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class EarningCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    date: date_type
    source_type: EarningType
    source_id: uuid.UUID | None = None
    source_label: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_source_fields(self) -> "EarningCreate":
        if (
            self.source_type != "other"
            and self.source_id is None
            and not self.source_label
        ):
            raise ValueError(
                "Either source_id or source_label is required unless source_type is 'other'."
            )
        return self


class EarningUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    date: date_type | None = None
    source_type: EarningType | None = None
    source_id: uuid.UUID | None = None
    source_label: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


class EarningResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    transaction_id: uuid.UUID | None
    source_id: uuid.UUID | None
    source_type: str
    source_label: str | None
    source_name: str | None = None
    amount: Decimal
    currency: str
    date: date_type
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class EarningFilters(BaseModel):
    source_type: EarningType | None = None
    date_from: date_type | None = None
    date_to: date_type | None = None
    source_id: uuid.UUID | None = None


class ClassifyTransactionRequest(BaseModel):
    classification: ClassificationType
    source_type: EarningType | None = None
    source_id: uuid.UUID | None = None
    source_label: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_income_fields(self) -> "ClassifyTransactionRequest":
        if self.classification == "income" and self.source_type is None:
            raise ValueError("source_type is required when classification is 'income'.")
        return self
