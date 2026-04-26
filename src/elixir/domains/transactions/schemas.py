from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from elixir.shared.pagination import PagedResponse

TransactionType = Literal["debit", "credit", "transfer"]
TransactionSource = Literal[
    "manual",
    "statement_import",
    "recurring_detected",
    "bulk_import",
]
AccountKind = Literal["bank", "credit_card"]


class TransactionItemInput(BaseModel):
    category_id: uuid.UUID
    amount: Decimal
    label: str | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Item amount must be greater than 0.")
        return value


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    account_kind: AccountKind
    amount: Decimal
    currency: str = Field(default="INR", min_length=3, max_length=3)
    date: date
    type: TransactionType
    raw_description: str | None = None
    notes: str | None = None
    items: list[TransactionItemInput] = Field(min_length=1)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("Transaction amount must be greater than 0.")
        return value


class TransactionUpdate(BaseModel):
    notes: str | None = None
    type: TransactionType | None = None
    items: list[TransactionItemInput] | None = Field(default=None, min_length=1)


class TransactionFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    account_id: uuid.UUID | None = None
    type: TransactionType | None = None
    source: TransactionSource | None = None
    category_id: uuid.UUID | None = None
    search_text: str | None = None


class TransactionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    amount: Decimal
    currency: str
    label: str | None = None
    is_primary: bool
    updated_at: datetime | None = None


class TransactionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    account_kind: str
    amount: Decimal
    currency: str
    date: date
    type: str
    source: str
    raw_description: str | None = None
    notes: str | None = None
    account_name: str | None = None
    primary_category_id: uuid.UUID | None = None
    primary_category_name: str | None = None
    primary_category_icon: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    account_kind: str
    amount: Decimal
    currency: str
    date: date
    type: str
    source: str
    raw_description: str | None = None
    notes: str | None = None
    account_name: str | None = None
    items: list[TransactionItemResponse]
    created_at: datetime | None = None
    updated_at: datetime | None = None


TransactionListResponse = PagedResponse[TransactionSummary]
