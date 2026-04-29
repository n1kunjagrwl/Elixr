from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


_INSTRUMENT_TYPES = Literal[
    "stock",
    "mf",
    "etf",
    "fd",
    "ppf",
    "bond",
    "nps",
    "sgb",
    "crypto",
    "gold",
    "us_stock",
    "rd",
    "other",
]
_EXCHANGE_TYPES = Literal["NSE", "BSE", "NYSE", "NASDAQ", "MCX"]
_DATA_SOURCE_TYPES = Literal[
    "amfi", "eodhd", "coingecko", "twelve_data", "metals_api", "calculated"
]
_SIP_FREQUENCIES = Literal["monthly", "weekly", "quarterly"]
_COMPOUNDING_TYPES = Literal["monthly", "quarterly", "annually", "simple"]


# ── Instrument schemas ────────────────────────────────────────────────────────


class InstrumentCreate(BaseModel):
    name: str
    type: _INSTRUMENT_TYPES
    ticker: str | None = None
    isin: str | None = None
    exchange: _EXCHANGE_TYPES | None = None
    currency: str = "INR"
    data_source: _DATA_SOURCE_TYPES | None = None
    govt_rate_percent: Decimal | None = None


class InstrumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    ticker: str | None = None
    isin: str | None = None
    exchange: str | None = None
    currency: str
    data_source: str | None = None
    govt_rate_percent: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── Holding schemas ───────────────────────────────────────────────────────────


class HoldingCreate(BaseModel):
    instrument_id: uuid.UUID
    units: Decimal | None = None
    avg_cost_per_unit: Decimal | None = None
    total_invested: Decimal | None = None
    current_value: Decimal | None = None
    current_price: Decimal | None = None


class HoldingUpdate(BaseModel):
    units: Decimal | None = None
    avg_cost_per_unit: Decimal | None = None
    total_invested: Decimal | None = None
    current_value: Decimal | None = None
    current_price: Decimal | None = None


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    instrument_id: uuid.UUID
    units: Decimal | None = None
    avg_cost_per_unit: Decimal | None = None
    total_invested: Decimal | None = None
    current_value: Decimal | None = None
    current_price: Decimal | None = None
    last_valued_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── FD Details schemas ────────────────────────────────────────────────────────


class FDDetailsCreate(BaseModel):
    principal: Decimal
    rate_percent: Decimal
    tenure_days: int
    start_date: date
    maturity_date: date
    compounding: _COMPOUNDING_TYPES


class FDDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    holding_id: uuid.UUID
    principal: Decimal
    rate_percent: Decimal
    tenure_days: int
    start_date: date
    maturity_date: date
    compounding: str
    maturity_amount: Decimal | None = None
    created_at: datetime | None = None


# ── SIP schemas ───────────────────────────────────────────────────────────────


class SIPCreate(BaseModel):
    instrument_id: uuid.UUID
    amount: Decimal
    frequency: _SIP_FREQUENCIES
    debit_day: int | None = None
    bank_account_id: uuid.UUID | None = None


class SIPUpdate(BaseModel):
    amount: Decimal | None = None
    frequency: _SIP_FREQUENCIES | None = None
    debit_day: int | None = None
    bank_account_id: uuid.UUID | None = None


class SIPResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    instrument_id: uuid.UUID
    amount: Decimal
    frequency: str
    debit_day: int | None = None
    bank_account_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ── SIP confirm schema ────────────────────────────────────────────────────────


class SIPConfirmRequest(BaseModel):
    transaction_id: uuid.UUID


# ── Portfolio history schema ───────────────────────────────────────────────────


class PortfolioSnapshotResponse(BaseModel):
    snapshot_date: date
    total_value: Decimal
