# Domain: budgets

## Responsibility

Lets users set spending limits per category for a given time period, tracks cumulative spend against those limits in real time, and fires alerts when limits are approached (80%) or breached (100%). Budget periods are flexible — calendar month, week, or a fully custom date range — to accommodate users whose financial cycles don't align with calendar months (e.g., salary arrives on the 15th).

The domain reacts to categorised transactions passively via events. It never queries the `transactions` domain directly.

---

## Tables Owned

### `budget_goals`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `category_id` | `uuid` NOT NULL | → `categories.id` (no PG FK) |
| `limit_amount` | `numeric(15,2)` NOT NULL | Maximum spend allowed in this period |
| `currency` | `char(3)` NOT NULL DEFAULT `'INR'` | — |
| `period_type` | `text` NOT NULL | `monthly` \| `weekly` \| `custom` |
| `period_anchor_day` | `int` NULLABLE | For `monthly`: day of month the period starts (e.g., 15 for salary-aligned) |
| `custom_start` | `date` NULLABLE | For `period_type = custom` |
| `custom_end` | `date` NULLABLE | For `period_type = custom` |
| `rollover` | `bool` DEFAULT false | Reserved for future: carry unspent budget to next period |
| `is_active` | `bool` DEFAULT true | — |
| `created_at` | `timestamptz` | — |

**Period resolution logic** (computed in the service, not stored):
- `monthly` with no anchor: period = calendar month (1st–last day)
- `monthly` with `period_anchor_day = 15`: period runs 15th of current month to 14th of next month
- `weekly`: period = Monday–Sunday of the current week
- `custom`: use `custom_start` and `custom_end` literally

### `budget_progress`
Materialised tracking of current-period spend per goal. Recomputed on each `TransactionCategorized` event.

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `goal_id` | `uuid` FK → `budget_goals.id` | — |
| `user_id` | `uuid` NOT NULL | Denormalised for fast user-scoped queries |
| `period_start` | `date` NOT NULL | Current period start |
| `period_end` | `date` NOT NULL | Current period end |
| `current_spend` | `numeric(15,2)` NOT NULL DEFAULT 0 | Cumulative spend this period |
| `updated_at` | `timestamptz` | — |

### `budget_alerts`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `goal_id` | `uuid` FK → `budget_goals.id` | — |
| `triggered_at` | `timestamptz` NOT NULL | — |
| `threshold_percent` | `int` NOT NULL | `80` or `100` |
| `current_spend` | `numeric(15,2)` | Spend at the time the alert was triggered |
| `period_start` | `date` | Which period this alert belongs to |

Alerts are deduplicated per goal per period per threshold — only one 80% alert and one 100% alert fires per period per goal.

### `outbox`
Standard outbox table.

---

## SQL Views Exposed

None. Budget data is not queried cross-domain.

---

## Events Published

### `BudgetLimitWarning`
```python
@dataclass
class BudgetLimitWarning:
    event_type = "budgets.BudgetLimitWarning"
    goal_id: UUID
    user_id: UUID
    category_id: UUID
    current_spend: Decimal
    limit_amount: Decimal
    percent_used: float      # 0.80–0.99
    period_start: date
    period_end: date
```

### `BudgetLimitBreached`
```python
@dataclass
class BudgetLimitBreached:
    event_type = "budgets.BudgetLimitBreached"
    goal_id: UUID
    user_id: UUID
    category_id: UUID
    current_spend: Decimal
    limit_amount: Decimal
    period_start: date
    period_end: date
```

Both consumed by: `notifications`

---

## Events Subscribed

### `TransactionCategorized` (from `transactions`)

The core handler:

```
0. If transaction.type == 'transfer': skip entirely. Self-transfers are not expenses.

1. Find all active budget_goals for this user where goal.category_id is in the transaction's item categories

2. For each matching goal:
   a. Determine the current period for this goal (period_type resolution logic above)
   b. Check if the transaction.date falls within this period
   c. If not in period: skip

3. Upsert budget_progress for (goal_id, period_start):
   current_spend += fx.convert(item.amount, item.currency, goal.currency)
   (Convert item amount to the goal's currency at current FX rate before adding)

4. Compute percent_used = current_spend / limit_amount

5. If percent_used >= 1.0 AND no 100% alert exists for this goal+period:
   → Publish BudgetLimitBreached
   → Insert budget_alerts row (threshold=100)

6. If 0.8 <= percent_used < 1.0 AND no 80% alert exists for this goal+period:
   → Publish BudgetLimitWarning
   → Insert budget_alerts row (threshold=80)
```

Handler must be idempotent: check `budget_alerts` before publishing to avoid duplicate alerts if the same event is replayed.

### `TransactionUpdated` (from `transactions`)

Handles retroactive budget correction when the user re-categorizes a transaction.

```
0. If 'items' not in event.changed_fields: skip (only notes or type changed)
   If event.old_items is None or event.new_items is None: skip

1. For each item in old_items:
   Find active budget_goals for this user where goal.category_id == item.category_id
   For each matching goal:
     a. Determine the period for this goal that contains event.date
     b. If event.date not in any period: skip
     c. Decrement budget_progress.current_spend by fx.convert(item.amount, item.currency, goal.currency)
        (Never let current_spend go below 0 — floor at 0)

2. For each item in new_items:
   Find active budget_goals for this user where goal.category_id == item.category_id
   For each matching goal:
     a. Determine the period for this goal that contains event.date
     b. If event.date not in any period: skip
     c. Increment budget_progress.current_spend by fx.convert(item.amount, item.currency, goal.currency)

3. Recheck thresholds for all affected goals and fire alerts if newly breached (same deduplication logic as TransactionCategorized)
```

Idempotency note: the increment/decrement approach is not inherently idempotent. If this event is re-dispatched (at-least-once delivery), the delta is applied twice. To guard against this, the handler checks whether the transaction's current items in the DB already match `new_items` before applying the correction. If they match, the correction has already been applied — skip.

---

## Service Methods Exposed

None.

---

## Key Design Decisions

**`budget_progress` as a running counter, not a query.** An alternative design would be to compute `current_spend` on the fly from `transactions_with_categories` every time the dashboard loads. This would require a cross-domain view query spanning potentially thousands of transactions. Instead, `budget_progress` is maintained incrementally as each `TransactionCategorized` event arrives — the dashboard read is a single-row lookup.

**Deduplication of alerts via `budget_alerts` table.** Without deduplication, every transaction in an over-budget category would fire a new breach alert. The handler checks for an existing alert for the current goal + period + threshold before publishing.

**`period_anchor_day` for salary-aligned budgets.** A user paid on the 15th who wants to track "this month's" spending naturally thinks of the period as 15th–14th. Forcing calendar months would split one natural pay cycle across two budget periods, making the numbers feel wrong. The anchor day makes the period resolution genuinely personal.

**`rollover` reserved for future use.** The column exists to avoid a migration later. When implemented, a rollover budget would compute `effective_limit = limit_amount + (previous_period_unspent)` before checking thresholds.
