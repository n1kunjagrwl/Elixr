import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from elixir.shared.base import Base, IDMixin, MutableMixin, TimestampMixin


class BudgetGoal(Base, IDMixin, MutableMixin):
    __tablename__ = "budget_goals"
    __table_args__ = (
        CheckConstraint(
            "period_type IN ('monthly','weekly','custom')",
            name="ck_budget_goals_period_type",
        ),
        CheckConstraint(
            "period_anchor_day IS NULL OR (period_anchor_day >= 1 AND period_anchor_day <= 28)",
            name="ck_budget_goals_anchor_day",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_anchor_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    custom_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    rollover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BudgetProgress(Base, IDMixin, MutableMixin):
    __tablename__ = "budget_progress"
    __table_args__ = (
        UniqueConstraint(
            "goal_id", "period_start", name="uq_budget_progress_goal_period"
        ),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("budget_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    current_spend: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )


class BudgetAlert(Base, IDMixin, TimestampMixin):
    __tablename__ = "budget_alerts"
    __table_args__ = (
        UniqueConstraint(
            "goal_id",
            "period_start",
            "threshold_percent",
            name="uq_budget_alerts_goal_period_threshold",
        ),
        CheckConstraint(
            "threshold_percent IN (80, 100)",
            name="ck_budget_alerts_threshold_percent",
        ),
    )

    goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("budget_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    current_spend: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)


class BudgetsOutbox(Base, IDMixin, TimestampMixin):
    __tablename__ = "budgets_outbox"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
