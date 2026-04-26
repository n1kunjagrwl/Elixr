import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, MutableMixin, TimestampMixin


_INSTRUMENT_TYPES = (
    "stock", "mf", "etf", "fd", "ppf", "bond", "nps", "sgb", "crypto", "gold",
    "us_stock", "rd", "other",
)
_EXCHANGES = ("NSE", "BSE", "NYSE", "NASDAQ", "MCX")
_DATA_SOURCES = ("amfi", "eodhd", "coingecko", "twelve_data", "metals_api", "calculated")
_SIP_FREQUENCIES = ("monthly", "weekly", "quarterly")
_COMPOUNDING_TYPES = ("monthly", "quarterly", "annually", "simple")


class Instrument(Base, IDMixin, MutableMixin):
    """Shared master registry — not per-user."""

    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint(
            "type IN ('stock','mf','etf','fd','ppf','bond','nps','sgb','crypto','gold',"
            "'us_stock','rd','other')",
            name="ck_instruments_type",
        ),
        CheckConstraint(
            "exchange IS NULL OR exchange IN ('NSE','BSE','NYSE','NASDAQ','MCX')",
            name="ck_instruments_exchange",
        ),
        CheckConstraint(
            "data_source IS NULL OR data_source IN "
            "('amfi','eodhd','coingecko','twelve_data','metals_api','calculated')",
            name="ck_instruments_data_source",
        ),
    )

    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(10), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    data_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    govt_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)


class Holding(Base, IDMixin, MutableMixin):
    """Per-user investment holding."""

    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("user_id", "instrument_id", name="uq_holdings_user_instrument"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    units: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    avg_cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    total_invested: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    last_valued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SIPRegistration(Base, IDMixin, MutableMixin):
    """Scheduled Investment Plan registration."""

    __tablename__ = "sip_registrations"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('monthly','weekly','quarterly')",
            name="ck_sip_registrations_frequency",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    debit_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ValuationSnapshot(Base, IDMixin, TimestampMixin):
    """Immutable daily valuation log — upserted."""

    __tablename__ = "valuation_snapshots"
    __table_args__ = (
        UniqueConstraint("holding_id", "snapshot_date", name="uq_valuation_snapshots_holding_date"),
    )

    holding_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("holdings.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)


class FDDetails(Base, IDMixin, TimestampMixin):
    """Fixed Deposit details — immutable (no updated_at)."""

    __tablename__ = "fd_details"
    __table_args__ = (
        CheckConstraint(
            "compounding IN ('monthly','quarterly','annually','simple')",
            name="ck_fd_details_compounding",
        ),
        UniqueConstraint("holding_id", name="uq_fd_details_holding"),
    )

    holding_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("holdings.id", ondelete="CASCADE"),
        nullable=False,
    )
    principal: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    tenure_days: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_date: Mapped[date] = mapped_column(Date, nullable=False)
    compounding: Mapped[str] = mapped_column(String(20), nullable=False)
    maturity_amount: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)


class InvestmentsOutbox(Base, IDMixin, TimestampMixin):
    """Outbox table for investments domain events."""

    __tablename__ = "investments_outbox"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
