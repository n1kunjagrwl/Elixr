import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ── Enums as literals ──────────────────────────────────────────────────────────

BalanceDirection = Literal["owed_to_me", "i_owe"]
BalanceStatus = Literal["open", "partial", "settled"]
SettlementMethod = Literal["cash", "upi", "bank_transfer", "other"]


# ── PeerContact schemas ────────────────────────────────────────────────────────


class PeerContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class PeerContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class PeerContactResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    phone: str | None
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ── PeerBalance schemas ────────────────────────────────────────────────────────


class PeerBalanceCreate(BaseModel):
    peer_id: uuid.UUID
    description: str = Field(..., min_length=1, max_length=500)
    original_amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    direction: BalanceDirection
    linked_transaction_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class PeerBalanceUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class PeerBalanceResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    peer_id: uuid.UUID
    description: str
    original_amount: Decimal
    settled_amount: Decimal
    remaining_amount: Decimal
    currency: str
    direction: str
    status: str
    linked_transaction_id: uuid.UUID | None
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


# ── PeerSettlement schemas ─────────────────────────────────────────────────────


class PeerSettlementCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    settled_at: datetime
    method: SettlementMethod | None = None
    linked_transaction_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class PeerSettlementResponse(BaseModel):
    id: uuid.UUID
    balance_id: uuid.UUID
    amount: Decimal
    currency: str
    settled_at: datetime
    method: str | None
    linked_transaction_id: uuid.UUID | None
    notes: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}
