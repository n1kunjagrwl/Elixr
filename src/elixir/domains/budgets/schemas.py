import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ── Type literals ──────────────────────────────────────────────────────────────

PeriodType = Literal["monthly", "weekly", "custom"]


# ── Request schemas ────────────────────────────────────────────────────────────


class BudgetGoalCreate(BaseModel):
    category_id: uuid.UUID
    limit_amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    period_type: PeriodType
    period_anchor_day: int | None = None
    custom_start: date | None = None
    custom_end: date | None = None
    rollover: bool = False


class BudgetGoalUpdate(BaseModel):
    limit_amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    period_type: PeriodType | None = None
    period_anchor_day: int | None = None
    custom_start: date | None = None
    custom_end: date | None = None
    rollover: bool | None = None


# ── Response schemas ───────────────────────────────────────────────────────────


class BudgetGoalResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    category_id: uuid.UUID
    limit_amount: Decimal
    currency: str
    period_type: str
    period_anchor_day: int | None
    custom_start: date | None
    custom_end: date | None
    rollover: bool
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class BudgetGoalWithProgress(BudgetGoalResponse):
    """Goal response enriched with current-period spend and period bounds."""

    current_spend: Decimal = Decimal("0.00")
    period_start: date | None = None
    period_end: date | None = None
