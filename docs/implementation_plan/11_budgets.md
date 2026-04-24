# Implementation Plan: budgets

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/budgets.md`](../domains/budgets.md)
- Data model: [`docs/data-model.md`](../data-model.md#budgets)
- User slices: 24-create-budget, 25-view-budget-status, 26-budget-alert-response, 42-edit-deactivate-budget

## Dependencies
- `identity` — JWT auth middleware
- `categorization` — `category_id` on `budget_goals` references `categories.id`; validate via `categories_for_user` view
- `transactions` — publishes `TransactionCategorized` and `TransactionUpdated` which `budgets` subscribes to
- `fx` — `convert()` service method called during `TransactionCategorized` handler to normalise foreign currency amounts before accumulating `budget_progress.current_spend`

All of `transactions` and `fx` must be running before budget event handlers can function.

## What to Build
Spending limit tracking per category with flexible period definitions (calendar month, week, or custom date range). The domain passively reacts to categorised transactions via events — it never queries the `transactions` domain directly. Fires 80% and 100% threshold alerts per goal per period, deduplicated via `budget_alerts`. Budget progress is maintained as a running counter (`budget_progress.current_spend`) so the dashboard read is a single-row lookup, not a scan of transaction history.

## Tables to Create
| Table | Key columns |
|---|---|
| `budget_goals` | `user_id`, `category_id` (no PG FK), `limit_amount`, `currency`, `period_type`, `period_anchor_day`, `custom_start`, `custom_end`, `rollover`, `is_active` |
| `budget_progress` | `goal_id` FK→`budget_goals.id`, `user_id`, `period_start`, `period_end`, `current_spend` |
| `budget_alerts` | `goal_id` FK→`budget_goals.id`, `triggered_at`, `threshold_percent`, `current_spend`, `period_start` |
| `budgets_outbox` | standard outbox schema |

**Unique constraints**:
- `UNIQUE (goal_id, period_start)` on `budget_progress` — upserted on each `TransactionCategorized` event
- `UNIQUE (goal_id, period_start, threshold_percent)` on `budget_alerts` — deduplication guard

`period_type` enum: `monthly | weekly | custom`
`threshold_percent` on `budget_alerts`: constrained to `80` or `100`

Note: `budget_alerts` is an immutable log (no `updated_at`). `budget_progress` has `updated_at` (it changes frequently).

## Events Published
| Event | Consumed by |
|---|---|
| `budgets.BudgetLimitWarning` | `notifications` |
| `budgets.BudgetLimitBreached` | `notifications` |

## Events Subscribed
| Event | Publisher | Handler |
|---|---|---|
| `transactions.TransactionCategorized` | `transactions` | Accumulate spend, check thresholds, fire alerts |
| `transactions.TransactionUpdated` | `transactions` | Retroactively correct spend when categories change |

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/budgets` | List all budget goals with current period progress |
| `POST` | `/budgets` | Create a budget goal |
| `GET` | `/budgets/{id}` | Get a single goal with progress for the current period |
| `PATCH` | `/budgets/{id}` | Edit a goal (limit, period type, anchor day) |
| `DELETE` | `/budgets/{id}` | Deactivate a goal (`is_active = false`) |

## Action Steps

### Step 1 — Create `models.py`
Define `BudgetGoal`, `BudgetProgress`, `BudgetAlert`, and `BudgetsOutbox`.
- `BudgetGoal`: `Base`, `IDMixin`, `MutableMixin`
  - `period_type`: `CheckConstraint` for `monthly | weekly | custom`
  - `category_id`: `uuid`, no PG FK (cross-domain)
  - `rollover`: `Boolean`, default `False` — reserved, not yet used
- `BudgetProgress`: `Base`, `IDMixin`, `MutableMixin`
  - FK to `BudgetGoal` (within-domain PG FK)
  - `user_id` denormalised for fast user-scoped queries
  - `current_spend`: `NUMERIC(15, 2)`, default `0`
- `BudgetAlert`: `Base`, `IDMixin`, `TimestampMixin` — immutable (no `updated_at`)
  - FK to `BudgetGoal`
  - `threshold_percent`: `Integer`, `CheckConstraint` for `IN (80, 100)`

### Step 2 — Create Alembic migration
`uv run alembic revision --autogenerate -m "budgets: add budget_goals, budget_progress, budget_alerts, budgets_outbox"`.
Confirm the unique constraints `(goal_id, period_start)` on `budget_progress` and `(goal_id, period_start, threshold_percent)` on `budget_alerts` are present.

### Step 3 — Create `repositories.py`
Key methods:
- `create_goal(user_id, **fields) -> BudgetGoal`
- `get_goal(user_id, goal_id) -> BudgetGoal | None`
- `list_goals(user_id, active_only=True) -> list[BudgetGoal]`
- `update_goal(goal, **fields) -> BudgetGoal`
- `deactivate_goal(goal) -> None` — `is_active = False`
- `upsert_progress(goal_id, user_id, period_start, period_end, delta: Decimal) -> BudgetProgress`
  - `INSERT ... ON CONFLICT (goal_id, period_start) DO UPDATE SET current_spend = current_spend + delta, updated_at = now()`
  - Never let `current_spend` go below 0 (use `GREATEST(current_spend + delta, 0)`)
- `get_progress(goal_id, period_start) -> BudgetProgress | None`
- `list_progress_for_user(user_id) -> list[BudgetProgress]` — for dashboard
- `alert_exists(goal_id, period_start, threshold_percent) -> bool` — deduplication check
- `create_alert(goal_id, threshold_percent, current_spend, period_start) -> BudgetAlert`
- `find_goals_for_categories(user_id, category_ids: list[UUID]) -> list[BudgetGoal]` — finds active goals matching any of the given category IDs

### Step 4 — Create `schemas.py`
- `BudgetGoalCreate` — category_id, limit_amount, currency, period_type, period_anchor_day (optional), custom_start (optional), custom_end (optional)
  - Validate: if `period_type='custom'`, both `custom_start` and `custom_end` must be provided
  - Validate: if `period_type='monthly'`, `period_anchor_day` should be 1–28 (optional, defaults to 1)
- `BudgetGoalUpdate` — limit_amount, currency, period_anchor_day, custom_start, custom_end, is_active (all optional)
- `BudgetProgressResponse` — goal_id, period_start, period_end, current_spend, percent_used, limit_amount, currency
- `BudgetGoalResponse` — includes current period progress (from `budget_progress`)
- `BudgetGoalWithProgress` — combines goal + progress for the list/detail endpoints

### Step 5 — Create `services.py`
- `create_goal(user_id, data: BudgetGoalCreate) -> BudgetGoalResponse`
  - Validate `category_id` is visible to user via `categories_for_user` view
  - Validate no duplicate active goal for same `(user_id, category_id)` — or allow and let user manage multiples?  (Ask before implementing if unclear.)
- `edit_goal(user_id, goal_id, data: BudgetGoalUpdate) -> BudgetGoalResponse`
- `deactivate_goal(user_id, goal_id) -> None`
- `list_goals_with_progress(user_id) -> list[BudgetGoalWithProgress]`
  - For each goal: resolve current period, look up `budget_progress`, compute `percent_used`
- `get_goal_with_progress(user_id, goal_id) -> BudgetGoalWithProgress`
- `_resolve_current_period(goal: BudgetGoal, as_of_date: date) -> tuple[date, date]`
  - `monthly` no anchor → (1st of month, last day of month)
  - `monthly` with anchor_day=15 → (15th current month, 14th next month)
  - `weekly` → Monday–Sunday of the current week
  - `custom` → (custom_start, custom_end)
- `_handle_transaction_categorized(transaction_id, user_id, date, items, session) -> None`
  - Called by the event handler
  - Skip if transaction `type == 'transfer'` (check via items context or re-read the transaction — clarify approach)
  - For each item: find active goals where `goal.category_id == item.category_id`
  - For each matching goal:
    1. Resolve current period; check if `transaction.date` falls within it
    2. Convert `item.amount` from `item.currency` to `goal.currency` via `fx.convert()`
    3. Upsert `budget_progress` with the converted delta
    4. Check thresholds: if `current_spend / limit_amount >= 1.0` and no 100% alert exists → write `BudgetLimitBreached` to outbox + insert `budget_alerts` row
    5. If `0.8 <= current_spend / limit_amount < 1.0` and no 80% alert exists → write `BudgetLimitWarning` to outbox + insert `budget_alerts` row
- `_handle_transaction_updated(transaction_id, user_id, date, old_items, new_items, changed_fields, session) -> None`
  - Skip if `'items' not in changed_fields` or items are None
  - Idempotency: check if the transaction's current items in DB already match `new_items`; if yes, skip
  - Decrement spend for old_items' categories (floor at 0 via `GREATEST`)
  - Increment spend for new_items' categories
  - Recheck thresholds for all affected goals

### Step 6 — Create `events.py`
```python
@dataclass
class BudgetLimitWarning:
    event_type: ClassVar[str] = "budgets.BudgetLimitWarning"
    goal_id: UUID; user_id: UUID; category_id: UUID
    current_spend: Decimal; limit_amount: Decimal
    percent_used: float; period_start: date; period_end: date

@dataclass
class BudgetLimitBreached:
    event_type: ClassVar[str] = "budgets.BudgetLimitBreached"
    goal_id: UUID; user_id: UUID; category_id: UUID
    current_spend: Decimal; limit_amount: Decimal
    period_start: date; period_end: date
```

Event handlers (subscribed):
```python
async def handle_transaction_categorized(payload: dict, session: AsyncSession) -> None:
    # idempotent: check budget_alerts before publishing duplicate alerts

async def handle_transaction_updated(payload: dict, session: AsyncSession) -> None:
    # idempotent: compare DB items to new_items before applying delta
```

### Step 7 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.budgets.events import handle_transaction_categorized, handle_transaction_updated
    event_bus.subscribe("transactions.TransactionCategorized", handle_transaction_categorized)
    event_bus.subscribe("transactions.TransactionUpdated", handle_transaction_updated)
    event_bus.register_outbox_table("budgets_outbox")

def get_temporal_workflows() -> list:
    return []  # budgets has no scheduled workflows

def get_temporal_activities(*args) -> list:
    return []
```

### Step 8 — Complete `api.py`
5 endpoints. Error mappings:
- `BudgetGoalNotFoundError` → 404
- `InvalidPeriodConfigError` → 422 (custom period missing dates, anchor day out of range)

### Step 9 — Register router in `runtime/app.py`
Include the `budgets` router under prefix `/budgets`.

## Verification Checklist
- [ ] Creating a monthly budget with `period_anchor_day=15` results in period 15th→14th correctly
- [ ] `TransactionCategorized` with `type='transfer'` is skipped entirely
- [ ] 80% alert fires exactly once per goal per period (deduplication via `budget_alerts`)
- [ ] 100% alert fires exactly once per goal per period
- [ ] `TransactionCategorized` replayed does not re-fire already-emitted alerts
- [ ] `TransactionUpdated` with only `notes` changed (no items change) is skipped
- [ ] `current_spend` never goes below 0 when items are removed via `TransactionUpdated`
- [ ] `fx.convert()` is called for every non-INR item before accumulating spend
- [ ] `GET /budgets` returns each goal with its current period's `percent_used`
- [ ] Ruff + mypy pass with no errors
