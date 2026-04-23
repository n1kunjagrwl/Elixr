# Slice: Create Budget Goal

## User Goal
Set a spending limit for a category over a defined time period so the app can track progress and alert when the limit is approached or exceeded.

## Trigger
User navigates to Budgets → Add Budget.

## Preconditions
- User is authenticated.
- At least one active category of kind `expense` exists.

## Steps

### Step 1: Select Category
**User action**: Picks an expense category from the active category list (e.g., "Food & Dining").
**System response**: Only `kind = 'expense'` categories are shown — income and transfer categories cannot have budgets.

### Step 2: Set Limit Amount and Currency
**User action**: Enters the spending limit (e.g., ₹5000) and currency (defaults to INR).
**System response**: Form validates amount > 0.

### Step 3: Choose Period Type
**User action**: Selects:
- **Monthly (calendar)**: period runs 1st–last day of each month.
- **Monthly (salary-aligned)**: period starts on a chosen day of month (e.g., day 15 → 15th of this month to 14th of next month). User sets `period_anchor_day`.
- **Weekly**: period runs Monday–Sunday.
- **Custom**: user provides `custom_start` and `custom_end` dates.

### Step 4: Budget Goal Created
**User action**: Taps "Save".
**System response**: A `budget_goals` row is inserted (`is_active = true`). A `budget_progress` row is created for the current period:
- `period_start` and `period_end` are computed from the period type.
- `current_spend = 0` (starts empty; historical transactions are not retroactively counted).

No event is published at creation — the budgets domain is purely reactive from this point.

### Step 5: Budget Starts Tracking
**User action**: None.
**System response**: From this point forward, every `TransactionCategorized` event for this user where an item's `category_id` matches this goal's `category_id` will:
1. Convert the item amount to the goal's currency via `fx.convert()` if needed.
2. Add the converted amount to `budget_progress.current_spend`.
3. Check if the 80% warning or 100% breach threshold is crossed and fire alerts if needed.

## Domains Involved
- **budgets**: Creates `budget_goals` and initial `budget_progress`.
- **categorization**: Provides the category list for the picker.
- **fx**: Called per transaction item for currency conversion.

## Edge Cases & Failures
- **Duplicate budget for same category + period type**: Allowed — a user can create two monthly Food & Dining budgets. This is unusual but not blocked. Both track independently.
- **Custom period end before start**: Validation error. `custom_end` must be > `custom_start`.
- **period_anchor_day = 31**: Rejected. Maximum is 28 to ensure the period start day exists in every month.
- **Budget created mid-period**: The `budget_progress.current_spend` starts at 0. Transactions from the current period that were imported before the budget was created are NOT retroactively counted. The user sees an accurate spend only from the moment the budget was created.

## Success Outcome
The budget goal is active and tracking. The user can see the current period's spend vs. limit on the budgets dashboard. Alerts will fire when the limit is approached or exceeded.
