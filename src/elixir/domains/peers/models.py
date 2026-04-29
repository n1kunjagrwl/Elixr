import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Computed, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, MutableMixin, TimestampMixin


class PeerContact(Base, IDMixin, MutableMixin):
    __tablename__ = "peer_contacts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class PeerBalance(Base, IDMixin, MutableMixin):
    __tablename__ = "peer_balances"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('owed_to_me','i_owe')",
            name="ck_peer_balances_direction",
        ),
        CheckConstraint(
            "status IN ('open','partial','settled')",
            name="ck_peer_balances_status",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    peer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("peer_contacts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    settled_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, server_default="0"
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        Computed("original_amount - settled_amount", persisted=True),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="INR"
    )
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="open"
    )
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class PeerSettlement(Base, IDMixin, TimestampMixin):
    __tablename__ = "peer_settlements"
    __table_args__ = (
        CheckConstraint(
            "method IS NULL OR method IN ('cash','upi','bank_transfer','other')",
            name="ck_peer_settlements_method",
        ),
    )

    balance_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("peer_balances.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="INR"
    )
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
