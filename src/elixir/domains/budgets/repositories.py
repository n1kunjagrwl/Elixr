import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.budgets.models import BudgetAlert, BudgetGoal, BudgetProgress, BudgetsOutbox


class BudgetsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── BudgetGoal ────────────────────────────────────────────────────────────

    async def create_goal(
        self,
        user_id: uuid.UUID,
        category_id: uuid.UUID,
        limit_amount: Decimal,
        currency: str = "INR",
        period_type: str = "monthly",
        period_anchor_day: int | None = None,
        custom_start: date | None = None,
        custom_end: date | None = None,
        rollover: bool = False,
    ) -> BudgetGoal:
        goal = BudgetGoal(
            user_id=user_id,
            category_id=category_id,
            limit_amount=limit_amount,
            currency=currency,
            period_type=period_type,
            period_anchor_day=period_anchor_day,
            custom_start=custom_start,
            custom_end=custom_end,
            rollover=rollover,
        )
        self._db.add(goal)
        await self._db.flush()
        return goal

    async def get_goal(
        self, user_id: uuid.UUID, goal_id: uuid.UUID
    ) -> BudgetGoal | None:
        result = await self._db.execute(
            select(BudgetGoal).where(
                BudgetGoal.id == goal_id,
                BudgetGoal.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_goals(self, user_id: uuid.UUID) -> list[BudgetGoal]:
        result = await self._db.execute(
            select(BudgetGoal)
            .where(BudgetGoal.user_id == user_id, BudgetGoal.is_active.is_(True))
            .order_by(BudgetGoal.created_at.asc())
        )
        return list(result.scalars().all())

    async def update_goal(self, goal: BudgetGoal, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(goal, key, value)
        goal.updated_at = datetime.now(timezone.utc)

    async def deactivate_goal(self, goal: BudgetGoal) -> None:
        goal.is_active = False
        goal.updated_at = datetime.now(timezone.utc)

    # ── BudgetProgress ────────────────────────────────────────────────────────

    async def get_progress(
        self, goal_id: uuid.UUID, period_start: date
    ) -> BudgetProgress | None:
        result = await self._db.execute(
            select(BudgetProgress).where(
                BudgetProgress.goal_id == goal_id,
                BudgetProgress.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def get_progress_for_period(
        self, goal_id: uuid.UUID, period_start: date
    ) -> BudgetProgress | None:
        """Return the progress row after an upsert (re-reads from session)."""
        result = await self._db.execute(
            select(BudgetProgress).where(
                BudgetProgress.goal_id == goal_id,
                BudgetProgress.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_progress(
        self,
        goal_id: uuid.UUID,
        user_id: uuid.UUID,
        period_start: date,
        period_end: date,
        delta: Decimal,
    ) -> None:
        """
        Insert or update current_spend using GREATEST(current_spend + delta, 0).
        Ensures spend never goes below zero (handles reversals gracefully).
        """
        await self._db.execute(
            text(
                """
                INSERT INTO budget_progress (id, goal_id, user_id, period_start, period_end,
                                             current_spend, created_at)
                VALUES (gen_random_uuid(), :goal_id, :user_id, :period_start, :period_end,
                        GREATEST(:delta, 0), now())
                ON CONFLICT (goal_id, period_start)
                DO UPDATE SET
                    current_spend = GREATEST(budget_progress.current_spend + :delta, 0),
                    updated_at = now()
                """
            ),
            {
                "goal_id": str(goal_id),
                "user_id": str(user_id),
                "period_start": period_start,
                "period_end": period_end,
                "delta": float(delta),
            },
        )

    # ── BudgetAlert ───────────────────────────────────────────────────────────

    async def alert_exists(
        self, goal_id: uuid.UUID, period_start: date, threshold_percent: int
    ) -> bool:
        result = await self._db.execute(
            select(BudgetAlert.id).where(
                BudgetAlert.goal_id == goal_id,
                BudgetAlert.period_start == period_start,
                BudgetAlert.threshold_percent == threshold_percent,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def insert_alert(
        self,
        goal_id: uuid.UUID,
        threshold_percent: int,
        current_spend: Decimal,
        period_start: date,
    ) -> BudgetAlert:
        alert = BudgetAlert(
            goal_id=goal_id,
            threshold_percent=threshold_percent,
            current_spend=current_spend,
            period_start=period_start,
            triggered_at=datetime.now(timezone.utc),
        )
        self._db.add(alert)
        await self._db.flush()
        return alert

    # ── Goal lookup by categories ─────────────────────────────────────────────

    async def find_goals_for_categories(
        self, user_id: uuid.UUID, category_ids: list[str]
    ) -> list[BudgetGoal]:
        """Return active goals matching any of the given category_ids for this user."""
        if not category_ids:
            return []
        cat_uuids = [uuid.UUID(cid) for cid in category_ids]
        result = await self._db.execute(
            select(BudgetGoal).where(
                BudgetGoal.user_id == user_id,
                BudgetGoal.is_active.is_(True),
                BudgetGoal.category_id.in_(cat_uuids),
            )
        )
        return list(result.scalars().all())

    # ── Outbox ────────────────────────────────────────────────────────────────

    async def add_outbox_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> None:
        row = BudgetsOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
