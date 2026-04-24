# Slice: Edit or Deactivate Budget Goal

## User Goal
Adjust a budget goal's spending limit or period settings to better reflect current spending habits, or deactivate a goal that is no longer relevant.

## Trigger
User navigates to the Budgets screen, taps a budget goal card, and selects "Edit goal" or "Deactivate goal".

## Preconditions
- User is authenticated.
- The `budget_goals` row exists, belongs to this user, and `is_active = true`.

## Steps

### Step 1: Open Goal Detail
**User action**: Taps a budget goal card on the Budgets screen.
**System response**: The goal detail screen shows:
- Category name and icon
- `limit_amount` and `currency`
- `period_type` (monthly / weekly / custom) and period configuration (`period_anchor_day`, `custom_start`, `custom_end`)
- Current period's `budget_progress` (spend vs. limit)
- An "Edit goal" button and a "Deactivate goal" button

---

## Editing a Budget Goal

### Step 2a: Open Edit Form
**User action**: Taps "Edit goal".
**System response**: A form opens pre-filled with:
- `limit_amount` — editable
- `period_type` — editable (monthly / weekly / custom)
- `period_anchor_day` — shown and editable when `period_type = monthly`
- `custom_start` and `custom_end` — shown and editable when `period_type = custom`

The goal's `category_id` and `currency` are shown read-only. Category and currency cannot be changed after creation. To track a different category, the user creates a new goal.

### Step 3a: Edit Goal Fields
**User action**: Changes `limit_amount` and/or period settings.

- **limit_amount**: Changing the spending limit takes effect immediately for all subsequent `TransactionCategorized` and `TransactionUpdated` event processing. The threshold check uses the stored `limit_amount` at the time each event is processed — so after saving, the new limit governs all future budget checks. Existing `budget_progress` rows are not modified; their `current_spend` values remain unchanged.
- **period_type / period_anchor_day**: Changing the period configuration changes how future events resolve the "current period" for this goal. The next `TransactionCategorized` event after the edit will create a new `budget_progress` row for the newly computed period (e.g., switching from a calendar month to a 15th-anchored month). Existing `budget_progress` rows for past periods remain in history but may represent period boundaries that no longer match the new configuration.
- **custom_start / custom_end**: Editable when `period_type = custom`. Changing these dates moves the goal's active window. If the new dates do not include today, no `budget_progress` row will match `period_start ≤ today ≤ period_end` and the goal will not appear on the active dashboard until a new transaction falls within the new custom range.

### Step 4a: Save Changes
**User action**: Taps "Save".
**System response**: The `budget_goals` row is updated in place. `updated_at` is refreshed. No events are published. No `budget_progress` rows are retroactively modified or deleted. The dashboard will reflect the new limit on next load.

---

## Deactivating a Budget Goal

### Step 2b: Confirm Deactivation
**User action**: Taps "Deactivate goal".
**System response**: A confirmation dialog appears:

> "Deactivate this budget? Spending history will be preserved. This goal will no longer track new transactions."

### Step 3b: Deactivation Confirmed
**User action**: Confirms deactivation.
**System response**: `budget_goals.is_active` is set to `false`. `updated_at` is refreshed. No events are published.

Immediate effects:
- The goal disappears from the active budget dashboard on next load (the dashboard queries only `is_active = true` goals).
- No further `TransactionCategorized` or `TransactionUpdated` events are processed for this goal. The handler checks `is_active` at the top of every event and skips inactive goals.
- No further `BudgetLimitWarning` or `BudgetLimitBreached` alerts are fired for this goal.

What is preserved:
- All `budget_progress` rows for past and current periods remain in the database. They are not deleted.
- All `budget_alerts` rows for this goal remain in the database.
- Historical data is accessible if the user navigates to "Past budgets" or a budget history view — the `budget_goals` row is still queryable by `id`, just filtered out of the active dashboard.

### Step 4b: Reactivation (Optional)
**User action**: Navigates to "Inactive goals" and taps "Reactivate".
**System response**: `budget_goals.is_active` is set back to `true`. The goal reappears on the active dashboard. The next `TransactionCategorized` event will resume processing for this goal. Note: transactions that occurred while the goal was inactive are not retroactively added to `budget_progress` — only new events trigger updates from the moment of reactivation onward.

## Domains Involved
- **budgets**: Owns `budget_goals`, `budget_progress`, `budget_alerts`; performs all updates; no events published on edit or deactivation.

## Edge Cases & Failures
- **Editing limit_amount mid-period**: The change applies to threshold checks from the moment of save onward. If the user reduces the limit and the current `budget_progress.current_spend` already exceeds the new limit, the next qualifying `TransactionCategorized` event will fire a `BudgetLimitBreached` alert (if one has not already been fired for this period+goal). Reducing the limit does not retroactively fire an alert for existing spend — alerts only fire when new event processing detects a breach.
- **Editing period_type creates a gap**: If the user changes from `monthly` (period 1–31 Jan) to `monthly` with `period_anchor_day = 15` (period 15 Jan–14 Feb), the `budget_progress` rows for 1–14 Jan remain under the old period boundaries. These are preserved in history and do not count toward the new period. There is no automatic reconciliation of historical progress rows when period configuration changes.
- **Deactivating a goal that fired a 100% alert this period**: The alert rows remain in `budget_alerts`. The goal is silently inactive — no notification is sent to the user about the deactivation itself.
- **Deactivating a goal with an in-flight `TransactionCategorized` event**: The outbox poller delivers events at-least-once. If an event was dispatched before the deactivation took effect, the handler will process it against the goal (including potentially firing a new alert). This is a narrow race condition accepted by the at-least-once delivery model. The next event after the deactivation will see `is_active = false` and skip cleanly.
- **Attempting to delete a budget goal (not just deactivate)**: Hard-deletion of a `budget_goals` row is not supported via the UI. Deactivation is the intended mechanism. This preserves historical `budget_progress` data for past-period reporting.

## Success Outcome
**Edit**: The updated `limit_amount` or period configuration takes effect immediately for future event processing. The dashboard reflects the new limit on next load.

**Deactivate**: The goal is removed from the active dashboard. All historical spend data is retained. No further alerts fire for this goal.
