from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.shared.events import EventPayload


# ── Event dataclasses ─────────────────────────────────────────────────────────

@dataclass
class BudgetLimitWarning:
    event_type: ClassVar[str] = "budgets.BudgetLimitWarning"

    goal_id: uuid.UUID
    user_id: uuid.UUID
    category_id: uuid.UUID
    current_spend: Decimal
    limit_amount: Decimal
    percent_used: int
    period_start: date
    period_end: date

    def to_payload(self) -> dict:
        return {
            "goal_id": str(self.goal_id),
            "user_id": str(self.user_id),
            "category_id": str(self.category_id),
            "current_spend": str(self.current_spend),
            "limit_amount": str(self.limit_amount),
            "percent_used": self.percent_used,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


@dataclass
class BudgetLimitBreached:
    event_type: ClassVar[str] = "budgets.BudgetLimitBreached"

    goal_id: uuid.UUID
    user_id: uuid.UUID
    category_id: uuid.UUID
    current_spend: Decimal
    limit_amount: Decimal
    percent_used: int
    period_start: date
    period_end: date

    def to_payload(self) -> dict:
        return {
            "goal_id": str(self.goal_id),
            "user_id": str(self.user_id),
            "category_id": str(self.category_id),
            "current_spend": str(self.current_spend),
            "limit_amount": str(self.limit_amount),
            "percent_used": self.percent_used,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


# ── Event handlers (subscribed via bootstrap) ─────────────────────────────────

async def handle_transaction_categorized(payload: EventPayload, session: AsyncSession) -> None:
    """
    Accumulate spend for budget goals when a transaction is categorised.
    Skip transfers. Check 80%/100% thresholds and fire deduplicated alerts.
    """
    from elixir.domains.budgets.services import BudgetsService

    service = BudgetsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    txn_date_str: str = payload.get("date") or payload.get("transaction_date") or ""
    from datetime import date as date_type
    txn_date = date_type.fromisoformat(txn_date_str)
    items = payload.get("items", [])
    transaction_type = payload.get("transaction_type", "debit")

    await service._handle_transaction_categorized(
        user_id=user_id,
        txn_date=txn_date,
        items=items,
        fx_service=None,  # FX service is not injected via events; handler falls back to same-currency pass-through
        transaction_type=transaction_type,
    )


async def handle_transaction_updated(payload: EventPayload, session: AsyncSession) -> None:
    """
    Adjust budget spend retroactively when a transaction's category changes.
    """
    from elixir.domains.budgets.services import BudgetsService

    service = BudgetsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    txn_date_str: str = payload.get("date") or payload.get("transaction_date") or ""
    from datetime import date as date_type
    txn_date = date_type.fromisoformat(txn_date_str)
    old_items = payload.get("old_items", [])
    new_items = payload.get("new_items", [])

    await service._handle_transaction_updated(
        user_id=user_id,
        txn_date=txn_date,
        old_items=old_items,
        new_items=new_items,
        fx_service=None,
    )
