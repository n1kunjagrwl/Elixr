"""
BudgetsService — spending limit tracking per category with flexible periods.

Period resolution is service-side (not stored). The service passively reacts
to categorised transaction events — it never queries the transactions table
directly.
"""
from __future__ import annotations

import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.budgets.events import BudgetLimitBreached, BudgetLimitWarning
from elixir.domains.budgets.repositories import BudgetsRepository
from elixir.domains.budgets.schemas import (
    BudgetGoalCreate,
    BudgetGoalUpdate,
    BudgetGoalWithProgress,
)
from elixir.shared.exceptions import BudgetGoalNotFoundError, InvalidPeriodConfigError


class BudgetsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = BudgetsRepository(db)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_goal(
        self, user_id: uuid.UUID, data: BudgetGoalCreate
    ) -> BudgetGoalWithProgress:
        self._validate_period_config(
            period_type=data.period_type,
            period_anchor_day=data.period_anchor_day,
            custom_start=data.custom_start,
            custom_end=data.custom_end,
        )
        goal = await self._repo.create_goal(
            user_id=user_id,
            category_id=data.category_id,
            limit_amount=data.limit_amount,
            currency=data.currency,
            period_type=data.period_type,
            period_anchor_day=data.period_anchor_day,
            custom_start=data.custom_start,
            custom_end=data.custom_end,
            rollover=data.rollover,
        )
        await self._db.commit()
        return self._build_response(goal)

    async def edit_goal(
        self,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        data: BudgetGoalUpdate,
    ) -> BudgetGoalWithProgress:
        goal = await self._repo.get_goal(user_id, goal_id)
        if goal is None:
            raise BudgetGoalNotFoundError(f"Budget goal {goal_id} not found.")

        update_fields = data.model_dump(exclude_unset=True, exclude_none=True)

        # Validate period config with merged values
        period_type = update_fields.get("period_type", goal.period_type)
        period_anchor_day = update_fields.get("period_anchor_day", goal.period_anchor_day)
        custom_start = update_fields.get("custom_start", goal.custom_start)
        custom_end = update_fields.get("custom_end", goal.custom_end)

        self._validate_period_config(
            period_type=period_type,
            period_anchor_day=period_anchor_day,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        if update_fields:
            await self._repo.update_goal(goal, **update_fields)
        await self._db.commit()
        return self._build_response(goal)

    async def deactivate_goal(self, user_id: uuid.UUID, goal_id: uuid.UUID) -> None:
        goal = await self._repo.get_goal(user_id, goal_id)
        if goal is None:
            raise BudgetGoalNotFoundError(f"Budget goal {goal_id} not found.")
        await self._repo.deactivate_goal(goal)
        await self._db.commit()

    async def list_goals(self, user_id: uuid.UUID) -> list[BudgetGoalWithProgress]:
        goals = await self._repo.list_goals(user_id)
        return [self._build_response(g) for g in goals]

    async def get_goal(
        self, user_id: uuid.UUID, goal_id: uuid.UUID
    ) -> BudgetGoalWithProgress:
        goal = await self._repo.get_goal(user_id, goal_id)
        if goal is None:
            raise BudgetGoalNotFoundError(f"Budget goal {goal_id} not found.")
        return self._build_response(goal)

    # ── Period resolution ─────────────────────────────────────────────────────

    def _resolve_current_period(
        self, goal: Any, as_of_date: date
    ) -> tuple[date, date]:
        """
        Compute (period_start, period_end) for the period containing as_of_date.

        Rules:
        - monthly + no anchor: (1st, last day) of current month
        - monthly + anchor_day=N: (Nth current month, (N-1)th next month)
          If as_of_date < anchor_day, the period started last month.
        - weekly: (Monday, Sunday) of week containing as_of_date
        - custom: (custom_start, custom_end) verbatim
        """
        if goal.period_type == "weekly":
            # Monday=0, Sunday=6 via isoweekday: Mon=1, Sun=7
            day_of_week = as_of_date.isoweekday()  # Monday=1 … Sunday=7
            period_start = as_of_date - timedelta(days=day_of_week - 1)
            period_end = period_start + timedelta(days=6)
            return period_start, period_end

        if goal.period_type == "custom":
            return goal.custom_start, goal.custom_end

        # monthly
        anchor = goal.period_anchor_day
        if anchor is None:
            # Start = 1st of current month
            period_start = date(as_of_date.year, as_of_date.month, 1)
            last_day = calendar.monthrange(as_of_date.year, as_of_date.month)[1]
            period_end = date(as_of_date.year, as_of_date.month, last_day)
            return period_start, period_end

        # Monthly with anchor day
        if as_of_date.day >= anchor:
            # Period started this month on the anchor day
            period_start = date(as_of_date.year, as_of_date.month, anchor)
            # End = anchor_day - 1 of next month
            if as_of_date.month == 12:
                end_month_year = (as_of_date.year + 1, 1)
            else:
                end_month_year = (as_of_date.year, as_of_date.month + 1)
            period_end = date(end_month_year[0], end_month_year[1], anchor - 1)
        else:
            # Period started last month on the anchor day
            if as_of_date.month == 1:
                start_month_year = (as_of_date.year - 1, 12)
            else:
                start_month_year = (as_of_date.year, as_of_date.month - 1)
            period_start = date(start_month_year[0], start_month_year[1], anchor)
            period_end = date(as_of_date.year, as_of_date.month, anchor - 1)

        return period_start, period_end

    # ── Event handlers ────────────────────────────────────────────────────────

    async def _handle_transaction_categorized(
        self,
        user_id: uuid.UUID,
        txn_date: date,
        items: list[dict[str, Any]],
        fx_service: Any | None,
        transaction_type: str = "debit",
    ) -> None:
        """
        Accumulate spend for each matching budget goal.
        Skips transfers. Fires 80%/100% alerts (deduplicated).
        """
        if transaction_type == "transfer":
            return

        if not items:
            return

        category_ids = [item["category_id"] for item in items]
        goals = await self._repo.find_goals_for_categories(user_id, category_ids)

        if not goals:
            return

        # Build quick lookup: category_id → items
        items_by_category: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            cid = item["category_id"]
            items_by_category.setdefault(cid, []).append(item)

        for goal in goals:
            cat_str = str(goal.category_id)
            matching_items = items_by_category.get(cat_str, [])
            if not matching_items:
                continue

            period_start, period_end = self._resolve_current_period(goal, txn_date)

            # Check that transaction date falls within the period
            if not (period_start <= txn_date <= period_end):
                continue

            # Sum converted amounts for matching items
            delta = Decimal("0")
            for item in matching_items:
                item_amount = Decimal(str(item["amount"]))
                item_currency = item.get("currency", goal.currency)
                if fx_service is not None and item_currency != goal.currency:
                    converted = await fx_service.convert(
                        item_amount, item_currency, goal.currency, txn_date
                    )
                else:
                    converted = item_amount
                delta += converted

            await self._repo.upsert_progress(
                goal_id=goal.id,
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                delta=delta,
            )

            # Re-read progress to get updated current_spend
            progress = await self._repo.get_progress_for_period(goal.id, period_start)
            if progress is None:
                continue

            current_spend = progress.current_spend
            await self._check_and_fire_alerts(
                goal=goal,
                current_spend=current_spend,
                period_start=period_start,
                period_end=period_end,
                user_id=user_id,
            )

    async def _handle_transaction_updated(
        self,
        user_id: uuid.UUID,
        txn_date: date,
        old_items: list[dict[str, Any]],
        new_items: list[dict[str, Any]],
        fx_service: Any | None,
    ) -> None:
        """
        Retroactively adjust spend when a transaction's category changes.
        Reverses old items (negative delta) and applies new items (positive delta).
        """
        # Reverse old spend
        if old_items:
            old_category_ids = [item["category_id"] for item in old_items]
            old_goals = await self._repo.find_goals_for_categories(user_id, old_category_ids)
            old_items_by_category: dict[str, list[dict[str, Any]]] = {}
            for item in old_items:
                cid = item["category_id"]
                old_items_by_category.setdefault(cid, []).append(item)

            for goal in old_goals:
                cat_str = str(goal.category_id)
                matching = old_items_by_category.get(cat_str, [])
                if not matching:
                    continue
                period_start, period_end = self._resolve_current_period(goal, txn_date)
                if not (period_start <= txn_date <= period_end):
                    continue
                delta = Decimal("0")
                for item in matching:
                    item_amount = Decimal(str(item["amount"]))
                    item_currency = item.get("currency", goal.currency)
                    if fx_service is not None and item_currency != goal.currency:
                        converted = await fx_service.convert(
                            item_amount, item_currency, goal.currency, txn_date
                        )
                    else:
                        converted = item_amount
                    delta += converted
                # Reverse: negative delta
                await self._repo.upsert_progress(
                    goal_id=goal.id,
                    user_id=user_id,
                    period_start=period_start,
                    period_end=period_end,
                    delta=-delta,
                )

        # Apply new spend
        if new_items:
            new_category_ids = [item["category_id"] for item in new_items]
            new_goals = await self._repo.find_goals_for_categories(user_id, new_category_ids)
            new_items_by_category: dict[str, list[dict[str, Any]]] = {}
            for item in new_items:
                cid = item["category_id"]
                new_items_by_category.setdefault(cid, []).append(item)

            for goal in new_goals:
                cat_str = str(goal.category_id)
                matching = new_items_by_category.get(cat_str, [])
                if not matching:
                    continue
                period_start, period_end = self._resolve_current_period(goal, txn_date)
                if not (period_start <= txn_date <= period_end):
                    continue
                delta = Decimal("0")
                for item in matching:
                    item_amount = Decimal(str(item["amount"]))
                    item_currency = item.get("currency", goal.currency)
                    if fx_service is not None and item_currency != goal.currency:
                        converted = await fx_service.convert(
                            item_amount, item_currency, goal.currency, txn_date
                        )
                    else:
                        converted = item_amount
                    delta += converted
                await self._repo.upsert_progress(
                    goal_id=goal.id,
                    user_id=user_id,
                    period_start=period_start,
                    period_end=period_end,
                    delta=delta,
                )
                progress = await self._repo.get_progress_for_period(goal.id, period_start)
                if progress is None:
                    continue
                await self._check_and_fire_alerts(
                    goal=goal,
                    current_spend=progress.current_spend,
                    period_start=period_start,
                    period_end=period_end,
                    user_id=user_id,
                )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _validate_period_config(
        self,
        period_type: str,
        period_anchor_day: int | None,
        custom_start: date | None,
        custom_end: date | None,
    ) -> None:
        if period_type == "custom" and (custom_start is None or custom_end is None):
            raise InvalidPeriodConfigError(
                "Custom period requires both custom_start and custom_end."
            )
        if period_anchor_day is not None and not (1 <= period_anchor_day <= 28):
            raise InvalidPeriodConfigError(
                f"period_anchor_day must be between 1 and 28, got {period_anchor_day}."
            )

    async def _check_and_fire_alerts(
        self,
        goal: Any,
        current_spend: Decimal,
        period_start: date,
        period_end: date,
        user_id: uuid.UUID,
    ) -> None:
        """Check spend thresholds and write deduplicated alert outbox events."""
        limit = goal.limit_amount
        if limit <= 0:
            return

        percent_used = int((current_spend / limit) * 100)

        if current_spend >= limit:
            # 100% threshold
            already = await self._repo.alert_exists(goal.id, period_start, 100)
            if not already:
                await self._repo.insert_alert(
                    goal_id=goal.id,
                    threshold_percent=100,
                    current_spend=current_spend,
                    period_start=period_start,
                )
                breached_event = BudgetLimitBreached(
                    goal_id=goal.id,
                    user_id=user_id,
                    category_id=goal.category_id,
                    current_spend=current_spend,
                    limit_amount=limit,
                    percent_used=percent_used,
                    period_start=period_start,
                    period_end=period_end,
                )
                await self._repo.add_outbox_event(
                    BudgetLimitBreached.event_type, breached_event.to_payload()
                )
        elif current_spend >= Decimal("0.8") * limit:
            # 80% threshold
            already = await self._repo.alert_exists(goal.id, period_start, 80)
            if not already:
                await self._repo.insert_alert(
                    goal_id=goal.id,
                    threshold_percent=80,
                    current_spend=current_spend,
                    period_start=period_start,
                )
                warning_event = BudgetLimitWarning(
                    goal_id=goal.id,
                    user_id=user_id,
                    category_id=goal.category_id,
                    current_spend=current_spend,
                    limit_amount=limit,
                    percent_used=percent_used,
                    period_start=period_start,
                    period_end=period_end,
                )
                await self._repo.add_outbox_event(
                    BudgetLimitWarning.event_type, warning_event.to_payload()
                )

    def _build_response(self, goal: Any) -> BudgetGoalWithProgress:
        """Build a BudgetGoalWithProgress from a BudgetGoal ORM model."""
        today = date.today()
        try:
            period_start, period_end = self._resolve_current_period(goal, today)
        except Exception:
            period_start = None
            period_end = None

        return BudgetGoalWithProgress(
            id=goal.id,
            user_id=goal.user_id,
            category_id=goal.category_id,
            limit_amount=goal.limit_amount,
            currency=goal.currency,
            period_type=goal.period_type,
            period_anchor_day=goal.period_anchor_day,
            custom_start=goal.custom_start,
            custom_end=goal.custom_end,
            rollover=goal.rollover,
            is_active=goal.is_active,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            current_spend=Decimal("0.00"),
            period_start=period_start,
            period_end=period_end,
        )
