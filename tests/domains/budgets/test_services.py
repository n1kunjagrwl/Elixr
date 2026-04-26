"""
Service-layer tests for the budgets domain.

All external dependencies (DB session, repository, fx service) are mocked.
No real database or network connections are made.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_service(mock_db):
    from elixir.domains.budgets.services import BudgetsService
    return BudgetsService(db=mock_db)


def _make_goal(
    goal_id=None,
    user_id=None,
    category_id=None,
    limit_amount=Decimal("10000.00"),
    currency="INR",
    period_type="monthly",
    period_anchor_day=None,
    custom_start=None,
    custom_end=None,
    rollover=False,
    is_active=True,
):
    goal = MagicMock()
    goal.id = goal_id or uuid.uuid4()
    goal.user_id = user_id or USER_ID
    goal.category_id = category_id or uuid.uuid4()
    goal.limit_amount = limit_amount
    goal.currency = currency
    goal.period_type = period_type
    goal.period_anchor_day = period_anchor_day
    goal.custom_start = custom_start
    goal.custom_end = custom_end
    goal.rollover = rollover
    goal.is_active = is_active
    goal.created_at = datetime.now(timezone.utc)
    goal.updated_at = None
    return goal


def _make_progress(goal_id=None, period_start=None, period_end=None, current_spend=Decimal("0.00")):
    progress = MagicMock()
    progress.id = uuid.uuid4()
    progress.goal_id = goal_id or uuid.uuid4()
    progress.user_id = USER_ID
    progress.period_start = period_start or date(2026, 4, 1)
    progress.period_end = period_end or date(2026, 4, 30)
    progress.current_spend = current_spend
    progress.updated_at = None
    return progress


# ── TestCreateGoal ─────────────────────────────────────────────────────────────

class TestCreateGoal:
    async def test_create_goal_creates_goal(self, mock_db):
        """Happy path: creating a goal persists the row and commits."""
        from elixir.domains.budgets.schemas import BudgetGoalCreate

        svc = _make_service(mock_db)
        goal = _make_goal()

        data = BudgetGoalCreate(
            category_id=goal.category_id,
            limit_amount=Decimal("10000.00"),
            period_type="monthly",
        )

        with patch.object(svc._repo, "create_goal", new=AsyncMock(return_value=goal)), \
             patch.object(svc._repo, "get_progress", new=AsyncMock(return_value=None)):

            result = await svc.create_goal(USER_ID, data)

        assert result.id == goal.id
        assert result.limit_amount == Decimal("10000.00")
        mock_db.commit.assert_called_once()

    async def test_create_goal_custom_period_without_dates_raises_422(self, mock_db):
        """Custom period without custom_start/custom_end raises InvalidPeriodConfigError."""
        from elixir.domains.budgets.schemas import BudgetGoalCreate
        from elixir.shared.exceptions import InvalidPeriodConfigError

        svc = _make_service(mock_db)
        data = BudgetGoalCreate(
            category_id=uuid.uuid4(),
            limit_amount=Decimal("5000.00"),
            period_type="custom",
            # no custom_start or custom_end
        )

        with pytest.raises(InvalidPeriodConfigError):
            await svc.create_goal(USER_ID, data)

    async def test_create_goal_monthly_anchor_day_out_of_range_raises_422(self, mock_db):
        """anchor_day outside 1-28 raises InvalidPeriodConfigError."""
        from elixir.domains.budgets.schemas import BudgetGoalCreate
        from elixir.shared.exceptions import InvalidPeriodConfigError

        svc = _make_service(mock_db)

        data = BudgetGoalCreate(
            category_id=uuid.uuid4(),
            limit_amount=Decimal("5000.00"),
            period_type="monthly",
            period_anchor_day=29,  # out of range
        )

        with pytest.raises(InvalidPeriodConfigError):
            await svc.create_goal(USER_ID, data)

        data_low = BudgetGoalCreate(
            category_id=uuid.uuid4(),
            limit_amount=Decimal("5000.00"),
            period_type="monthly",
            period_anchor_day=0,  # too low
        )
        with pytest.raises(InvalidPeriodConfigError):
            await svc.create_goal(USER_ID, data_low)


# ── TestEditGoal ───────────────────────────────────────────────────────────────

class TestEditGoal:
    async def test_edit_goal_updates_fields(self, mock_db):
        """Happy path: editing a goal updates the limit_amount field."""
        from elixir.domains.budgets.schemas import BudgetGoalUpdate

        svc = _make_service(mock_db)
        goal = _make_goal()
        goal_id = goal.id

        data = BudgetGoalUpdate(limit_amount=Decimal("20000.00"))

        with patch.object(svc._repo, "get_goal", new=AsyncMock(return_value=goal)), \
             patch.object(svc._repo, "update_goal", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "get_progress", new=AsyncMock(return_value=None)):

            result = await svc.edit_goal(USER_ID, goal_id, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_edit_goal_not_found_raises_404(self, mock_db):
        """When goal not found, BudgetGoalNotFoundError is raised."""
        from elixir.domains.budgets.schemas import BudgetGoalUpdate
        from elixir.shared.exceptions import BudgetGoalNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_goal", new=AsyncMock(return_value=None)):
            with pytest.raises(BudgetGoalNotFoundError):
                await svc.edit_goal(USER_ID, uuid.uuid4(), BudgetGoalUpdate())


# ── TestDeactivateGoal ─────────────────────────────────────────────────────────

class TestDeactivateGoal:
    async def test_deactivate_goal_sets_is_active_false(self, mock_db):
        """Deactivating a goal sets is_active = False and commits."""
        svc = _make_service(mock_db)
        goal = _make_goal()
        goal_id = goal.id

        with patch.object(svc._repo, "get_goal", new=AsyncMock(return_value=goal)), \
             patch.object(svc._repo, "deactivate_goal", new=AsyncMock(return_value=None)):

            await svc.deactivate_goal(USER_ID, goal_id)

        mock_db.commit.assert_called_once()


# ── TestListGoals ──────────────────────────────────────────────────────────────

class TestListGoals:
    async def test_list_goals_returns_goals_with_progress(self, mock_db):
        """list_goals returns a list of BudgetGoalWithProgress responses."""
        svc = _make_service(mock_db)
        goals = [_make_goal(), _make_goal()]

        with patch.object(svc._repo, "list_goals", new=AsyncMock(return_value=goals)), \
             patch.object(svc._repo, "get_progress", new=AsyncMock(return_value=None)):

            results = await svc.list_goals(USER_ID)

        assert len(results) == 2


# ── TestGetGoal ───────────────────────────────────────────────────────────────

class TestGetGoal:
    async def test_get_goal_with_progress_returns_goal(self, mock_db):
        """get_goal returns a BudgetGoalWithProgress response."""
        svc = _make_service(mock_db)
        goal = _make_goal()

        with patch.object(svc._repo, "get_goal", new=AsyncMock(return_value=goal)), \
             patch.object(svc._repo, "get_progress", new=AsyncMock(return_value=None)):

            result = await svc.get_goal(USER_ID, goal.id)

        assert result.id == goal.id

    async def test_get_goal_not_found_raises_404(self, mock_db):
        """get_goal raises BudgetGoalNotFoundError when goal is missing."""
        from elixir.shared.exceptions import BudgetGoalNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_goal", new=AsyncMock(return_value=None)):
            with pytest.raises(BudgetGoalNotFoundError):
                await svc.get_goal(USER_ID, uuid.uuid4())


# ── TestResolvePeriod ─────────────────────────────────────────────────────────

class TestResolvePeriod:
    def _get_service(self, mock_db):
        from elixir.domains.budgets.services import BudgetsService
        return BudgetsService(db=mock_db)

    async def test_resolve_period_monthly_no_anchor(self, mock_db):
        """monthly with no anchor: (1st, last day) of current month."""
        svc = self._get_service(mock_db)
        goal = _make_goal(period_type="monthly", period_anchor_day=None)
        as_of = date(2026, 4, 15)

        start, end = svc._resolve_current_period(goal, as_of)

        assert start == date(2026, 4, 1)
        assert end == date(2026, 4, 30)

    async def test_resolve_period_monthly_with_anchor_day_15(self, mock_db):
        """monthly with anchor_day=15: (15th current month, 14th next month)."""
        svc = self._get_service(mock_db)
        goal = _make_goal(period_type="monthly", period_anchor_day=15)
        as_of = date(2026, 4, 20)

        start, end = svc._resolve_current_period(goal, as_of)

        assert start == date(2026, 4, 15)
        assert end == date(2026, 5, 14)

    async def test_resolve_period_weekly(self, mock_db):
        """weekly: (Monday, Sunday) of the week containing as_of_date."""
        svc = self._get_service(mock_db)
        goal = _make_goal(period_type="weekly")
        # 2026-04-22 is a Wednesday
        as_of = date(2026, 4, 22)

        start, end = svc._resolve_current_period(goal, as_of)

        # Monday = 2026-04-20, Sunday = 2026-04-26
        assert start == date(2026, 4, 20)
        assert end == date(2026, 4, 26)

    async def test_resolve_period_custom(self, mock_db):
        """custom: uses custom_start and custom_end from the goal."""
        svc = self._get_service(mock_db)
        goal = _make_goal(
            period_type="custom",
            custom_start=date(2026, 1, 1),
            custom_end=date(2026, 12, 31),
        )
        as_of = date(2026, 4, 15)

        start, end = svc._resolve_current_period(goal, as_of)

        assert start == date(2026, 1, 1)
        assert end == date(2026, 12, 31)


# ── TestHandleTransactionCategorized ─────────────────────────────────────────

class TestHandleTransactionCategorized:
    async def test_handle_transaction_categorized_accumulates_spend(self, mock_db):
        """Matching transaction: upsert_progress is called with delta."""
        svc = _make_service(mock_db)
        category_id = uuid.uuid4()
        goal = _make_goal(category_id=category_id, limit_amount=Decimal("10000.00"))

        mock_fx = AsyncMock()
        mock_fx.convert = AsyncMock(return_value=Decimal("500.00"))

        items = [{"category_id": str(category_id), "amount": "500.00", "currency": "INR"}]
        mock_upsert = AsyncMock(return_value=None)

        with patch.object(svc._repo, "find_goals_for_categories", new=AsyncMock(return_value=[goal])), \
             patch.object(svc._repo, "upsert_progress", new=mock_upsert), \
             patch.object(svc._repo, "get_progress_for_period", new=AsyncMock(return_value=_make_progress(current_spend=Decimal("500.00")))), \
             patch.object(svc._repo, "alert_exists", new=AsyncMock(return_value=False)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(return_value=None)):

            await svc._handle_transaction_categorized(
                user_id=USER_ID,
                txn_date=date(2026, 4, 15),
                items=items,
                fx_service=mock_fx,
            )

        mock_upsert.assert_called_once()

    async def test_handle_transaction_categorized_fires_80_percent_alert(self, mock_db):
        """When spend reaches 80% of limit, BudgetLimitWarning is written to outbox."""
        svc = _make_service(mock_db)
        category_id = uuid.uuid4()
        goal = _make_goal(category_id=category_id, limit_amount=Decimal("10000.00"))

        mock_fx = AsyncMock()
        mock_fx.convert = AsyncMock(return_value=Decimal("500.00"))

        items = [{"category_id": str(category_id), "amount": "500.00", "currency": "INR"}]
        outbox_calls = []

        with patch.object(svc._repo, "find_goals_for_categories", new=AsyncMock(return_value=[goal])), \
             patch.object(svc._repo, "upsert_progress", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "get_progress_for_period", new=AsyncMock(
                 return_value=_make_progress(current_spend=Decimal("8500.00"))
             )), \
             patch.object(svc._repo, "alert_exists", new=AsyncMock(return_value=False)), \
             patch.object(svc._repo, "insert_alert", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(
                 side_effect=lambda et, p: outbox_calls.append((et, p))
             )):

            await svc._handle_transaction_categorized(
                user_id=USER_ID,
                txn_date=date(2026, 4, 15),
                items=items,
                fx_service=mock_fx,
            )

        # Should fire 80% warning (8500 >= 8000 = 0.8 * 10000, but < 10000)
        warning_events = [e for e, _ in outbox_calls if e == "budgets.BudgetLimitWarning"]
        assert len(warning_events) == 1

    async def test_handle_transaction_categorized_fires_100_percent_alert(self, mock_db):
        """When spend reaches 100% of limit, BudgetLimitBreached is written to outbox."""
        svc = _make_service(mock_db)
        category_id = uuid.uuid4()
        goal = _make_goal(category_id=category_id, limit_amount=Decimal("10000.00"))

        mock_fx = AsyncMock()
        mock_fx.convert = AsyncMock(return_value=Decimal("500.00"))

        items = [{"category_id": str(category_id), "amount": "500.00", "currency": "INR"}]
        outbox_calls = []

        with patch.object(svc._repo, "find_goals_for_categories", new=AsyncMock(return_value=[goal])), \
             patch.object(svc._repo, "upsert_progress", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "get_progress_for_period", new=AsyncMock(
                 return_value=_make_progress(current_spend=Decimal("10500.00"))
             )), \
             patch.object(svc._repo, "alert_exists", new=AsyncMock(return_value=False)), \
             patch.object(svc._repo, "insert_alert", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(
                 side_effect=lambda et, p: outbox_calls.append((et, p))
             )):

            await svc._handle_transaction_categorized(
                user_id=USER_ID,
                txn_date=date(2026, 4, 15),
                items=items,
                fx_service=mock_fx,
            )

        breached_events = [e for e, _ in outbox_calls if e == "budgets.BudgetLimitBreached"]
        assert len(breached_events) == 1

    async def test_handle_transaction_categorized_alert_deduplication(self, mock_db):
        """When alert already exists, no new outbox event is written."""
        svc = _make_service(mock_db)
        category_id = uuid.uuid4()
        goal = _make_goal(category_id=category_id, limit_amount=Decimal("10000.00"))

        mock_fx = AsyncMock()
        mock_fx.convert = AsyncMock(return_value=Decimal("500.00"))

        items = [{"category_id": str(category_id), "amount": "500.00", "currency": "INR"}]
        outbox_calls = []

        with patch.object(svc._repo, "find_goals_for_categories", new=AsyncMock(return_value=[goal])), \
             patch.object(svc._repo, "upsert_progress", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "get_progress_for_period", new=AsyncMock(
                 return_value=_make_progress(current_spend=Decimal("10500.00"))
             )), \
             patch.object(svc._repo, "alert_exists", new=AsyncMock(return_value=True)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(
                 side_effect=lambda et, p: outbox_calls.append((et, p))
             )):

            await svc._handle_transaction_categorized(
                user_id=USER_ID,
                txn_date=date(2026, 4, 15),
                items=items,
                fx_service=mock_fx,
            )

        # Alert already exists — no outbox events should be written
        assert len(outbox_calls) == 0

    async def test_handle_transaction_categorized_skips_transfer(self, mock_db):
        """Transfer transactions are skipped — no upsert_progress called."""
        svc = _make_service(mock_db)
        category_id = uuid.uuid4()

        mock_fx = AsyncMock()
        items = [{"category_id": str(category_id), "amount": "500.00", "currency": "INR"}]
        mock_upsert = AsyncMock(return_value=None)

        with patch.object(svc._repo, "find_goals_for_categories", new=AsyncMock(return_value=[])), \
             patch.object(svc._repo, "upsert_progress", new=mock_upsert):

            await svc._handle_transaction_categorized(
                user_id=USER_ID,
                txn_date=date(2026, 4, 15),
                items=items,
                fx_service=mock_fx,
                transaction_type="transfer",
            )

        mock_upsert.assert_not_called()

    async def test_handle_transaction_updated_adjusts_spend(self, mock_db):
        """TransactionUpdated handler adjusts spend by reversing old and applying new."""
        svc = _make_service(mock_db)
        old_cat_id = uuid.uuid4()
        new_cat_id = uuid.uuid4()
        goal_old = _make_goal(category_id=old_cat_id, limit_amount=Decimal("10000.00"))
        goal_new = _make_goal(category_id=new_cat_id, limit_amount=Decimal("10000.00"))

        mock_fx = AsyncMock()
        mock_fx.convert = AsyncMock(return_value=Decimal("500.00"))

        old_items = [{"category_id": str(old_cat_id), "amount": "500.00", "currency": "INR"}]
        new_items = [{"category_id": str(new_cat_id), "amount": "500.00", "currency": "INR"}]

        call_count = 0

        async def side_effect_find(user_id, category_ids):
            nonlocal call_count
            call_count += 1
            if any(str(old_cat_id) == cid for cid in category_ids):
                return [goal_old]
            return [goal_new]

        mock_upsert = AsyncMock(return_value=None)
        with patch.object(svc._repo, "find_goals_for_categories", new=AsyncMock(side_effect=side_effect_find)), \
             patch.object(svc._repo, "upsert_progress", new=mock_upsert), \
             patch.object(svc._repo, "get_progress_for_period", new=AsyncMock(
                 return_value=_make_progress(current_spend=Decimal("500.00"))
             )), \
             patch.object(svc._repo, "alert_exists", new=AsyncMock(return_value=False)), \
             patch.object(svc._repo, "insert_alert", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(return_value=None)):

            await svc._handle_transaction_updated(
                user_id=USER_ID,
                txn_date=date(2026, 4, 15),
                old_items=old_items,
                new_items=new_items,
                fx_service=mock_fx,
            )

        # upsert_progress should be called twice: once to reverse old, once for new
        assert mock_upsert.call_count == 2
