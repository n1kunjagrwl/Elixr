import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ── Enums as literals ──────────────────────────────────────────────────────────

AccountType = Literal["savings", "current", "salary", "nre", "nro"]
CardNetwork = Literal["visa", "mastercard", "amex", "rupay"]


# ── Bank Account schemas ───────────────────────────────────────────────────────


class BankAccountCreate(BaseModel):
    nickname: str
    bank_name: str
    account_type: AccountType
    last4: str | None = Field(default=None, min_length=4, max_length=4)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class BankAccountUpdate(BaseModel):
    nickname: str | None = None
    bank_name: str | None = None
    account_type: AccountType | None = None
    last4: str | None = Field(default=None, min_length=4, max_length=4)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    nickname: str
    bank_name: str
    account_type: str
    last4: str | None
    currency: str
    is_active: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


# ── Credit Card schemas ────────────────────────────────────────────────────────


class CreditCardCreate(BaseModel):
    nickname: str
    bank_name: str
    card_network: CardNetwork | None = None
    last4: str | None = Field(default=None, min_length=4, max_length=4)
    credit_limit: Decimal | None = None
    billing_cycle_day: int | None = Field(default=None, ge=1, le=28)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class CreditCardUpdate(BaseModel):
    nickname: str | None = None
    bank_name: str | None = None
    card_network: CardNetwork | None = None
    last4: str | None = Field(default=None, min_length=4, max_length=4)
    credit_limit: Decimal | None = None
    billing_cycle_day: int | None = Field(default=None, ge=1, le=28)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


class CreditCardResponse(BaseModel):
    id: uuid.UUID
    nickname: str
    bank_name: str
    card_network: str | None
    last4: str | None
    credit_limit: Decimal | None
    billing_cycle_day: int | None
    currency: str
    is_active: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


# ── Account Summary schema (from user_accounts_summary view) ──────────────────


class AccountSummaryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    nickname: str
    bank_name: str
    account_kind: str  # "bank" | "credit_card"
    subtype: str | None
    last4: str | None
    currency: str
    is_active: bool

    model_config = {"from_attributes": True}
