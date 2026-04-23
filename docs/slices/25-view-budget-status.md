# Slice: View Budget Status Dashboard

## User Goal
See at a glance how much has been spent vs. the limit for each active budget goal in the current period.

## Trigger
User taps the "Budgets" tab in the app.

## Preconditions
- User has at least one active `budget_goals` row.
- At least one `budget_progress` row exists for the current period.

## Steps

### Step 1: Load Budget Dashboard
**User action**: Navigates to the Budgets screen.
**System response**: The API queries `budget_progress` for all active goals for this user where `period_start ≤ today ≤ period_end`. Each `budget_progress` row is a pre-computed running total — the read is a simple indexed lookup, not a cross-domain aggregation query.

For each goal, the response includes:
- Category name and icon (joined from `categories`)
- `limit_amount` (from `budget_goals`)
- `current_spend` (from `budget_progress`)
- `period_start` and `period_end`
- Computed `percent_used = current_spend / limit_amount`

### Step 2: View Progress Bars
**User action**: None — the screen renders.
**System response**: Each budget is rendered as a progress bar:
- 0–79%: green / neutral
- 80–99%: amber / warning (matches `BudgetLimitWarning` threshold)
- 100%+: red / breached (matches `BudgetLimitBreached` threshold)

The over-budget overage amount is shown (e.g., "₹200 over limit").

### Step 3: Tap a Budget for Detail
**User action**: Taps a budget card.
**System response**: A detail view shows:
- All transactions this period in this category (queried from `transactions_with_categories` view filtered by `category_id`, `user_id`, and date range `period_start–period_end`).
- A timeline of spend vs. limit over the period.
- Alert history for this goal from `budget_alerts` (when 80% was crossed, when 100% was crossed).

### Step 4: Navigate to Past Periods
**User action**: Taps "Previous period" arrow.
**System response**: The API computes the previous period's `period_start` and `period_end` from the goal's `period_type` and `period_anchor_day`. Queries `budget_progress` for the prior period. If a `budget_progress` row doesn't exist for the past period (budget was created after the period ended), a zero-spend placeholder is shown.

## Domains Involved
- **budgets**: Provides `budget_goals`, `budget_progress`, `budget_alerts`.
- **transactions**: Provides transaction detail for the drill-down view via `transactions_with_categories` view.
- **categorization**: Provides category names and icons.
- **fx**: Exchange rates embedded in `budget_progress.current_spend` (already converted to goal currency when spend was recorded).

## Edge Cases & Failures
- **No transactions yet in the current period**: `current_spend = 0`, progress bar shows 0%. Normal state for a new budget or start of a new period.
- **Goal period has changed since last `budget_progress` was written**: E.g., the user edited the budget's `period_anchor_day`. The next `TransactionCategorized` event will create a new `budget_progress` row for the corrected period. The old row remains in history.
- **Budget goal is inactive**: Inactive goals (`is_active = false`) are excluded from the dashboard. Their historical `budget_progress` rows remain but are not shown in the active view.
- **Multiple budgets for the same category**: Each is shown as a separate card with its own progress bar.

## Success Outcome
User sees a clear, real-time summary of spending vs. limits for every active budget, with drill-down to individual transactions.
