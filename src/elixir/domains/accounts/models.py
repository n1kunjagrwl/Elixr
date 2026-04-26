import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, MutableMixin, TimestampMixin

_ACCOUNT_TYPES = ("savings", "current", "salary", "nre", "nro")
_CARD_NETWORKS = ("visa", "mastercard", "amex", "rupay")


class BankAccount(Base, IDMixin, MutableMixin):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('savings','current','salary','nre','nro')",
            name="ck_bank_accounts_account_type",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CreditCard(Base, IDMixin, MutableMixin):
    __tablename__ = "credit_cards"
    __table_args__ = (
        CheckConstraint(
            "card_network IS NULL OR card_network IN ('visa','mastercard','amex','rupay')",
            name="ck_credit_cards_card_network",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    nickname: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    card_network: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    billing_cycle_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AccountsOutbox(Base, IDMixin, TimestampMixin):
    __tablename__ = "accounts_outbox"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
