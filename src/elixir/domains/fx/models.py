from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, TimestampMixin


class FXRate(Base, IDMixin, TimestampMixin):
    """
    Cached foreign exchange rate row.

    All rates are stored as X→INR (INR is the base currency).
    Non-INR pairs are triangulated at query time via FXService.convert().

    Rows are immutable log entries — upserted (not updated) on each refresh.
    There is no updated_at column by design.
    """

    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", name="uq_fx_rates_pair"),
    )

    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
