# Slice: Respond to Budget Warning or Breach Notification

## User Goal
React to a budget alert — review overspending, understand what triggered it, and decide whether to adjust the budget or curtail spending.

## Trigger
The user receives an in-app notification: "Approaching budget limit" (80%) or "Budget limit exceeded" (100%+).

## Preconditions
- A `BudgetLimitWarning` or `BudgetLimitBreached` event was published by the `budgets` domain.
- A notification row exists in the `notifications` table with deep-link `{"route": "/budgets", "goal_id": "{id}"}`.

## Steps

### Step 1: Receive Notification
**User action**: Sees the notification in the notification feed.
**System response for 80% warning**:
- Title: "Approaching budget limit"
- Body: "You've used {percent}% of your {category} budget (₹{spent} of ₹{limit}) this {period}."

**System response for 100% breach**:
- Title: "Budget limit exceeded"
- Body: "You've exceeded your {category} budget by ₹{overage}. Spent ₹{spent} against a ₹{limit} limit."

### Step 2: Tap Notification
**User action**: Taps the notification.
**System response**: Deep-links to the Budget detail screen for this specific goal (using `goal_id` from `metadata`). Shows the current period's progress bar, the over-budget amount, and the list of transactions in this category this period.

### Step 3: Review Spending
**User action**: Scrolls through the transaction list for this category in the current period.
**System response**: Transactions are shown with dates, descriptions, amounts, and item labels. The user can see exactly what pushed them over the limit.

### Step 4A: Adjust the Budget Limit
**User action**: Taps "Edit budget" and raises the `limit_amount`.
**System response**: `budget_goals.limit_amount` is updated. `budget_progress.current_spend` is unchanged. The next `TransactionCategorized` event will use the new limit for threshold checking. The `budget_alerts` rows for the current period remain — alerts already fired are not retracted when the limit increases.

### Step 4B: Re-Categorise a Transaction
**User action**: Taps a transaction and edits its category to move it out of this budget's category.
**System response**: `TransactionUpdated` is published. The `budgets` domain processes it: subtracts the old item amount from this goal's `budget_progress.current_spend`, adds to the new category's goal (if one exists). The budget progress bar updates automatically.

### Step 4C: Accept the Overspend
**User action**: Acknowledges the alert and takes no corrective action.
**System response**: The notification is marked read. The budget continues tracking. Only one 80% alert and one 100% alert will fire per goal per period (deduplicated via `budget_alerts` table) — no additional alerts for this goal in this period.

## Domains Involved
- **budgets**: Published the alert events, owns `budget_alerts` deduplication.
- **notifications**: Created and stores the notification.
- **transactions**: Provides the drill-down transaction list; processes edits.

## Edge Cases & Failures
- **Alert fired but spend is now under 80%** (e.g., user deleted a transaction after the alert): The alert remains in the notification feed. `budget_progress.current_spend` has been corrected by the `TransactionUpdated` retroactive handler, but the alert notification is not retracted — it reflects a past state.
- **Two 100% alerts in same period**: The `budget_alerts` deduplication check prevents this. Only one `threshold_percent = 100` row exists per goal per period. If a second `BudgetLimitBreached` would fire (e.g., due to event replay), the handler checks the existing `budget_alerts` row and skips the notification.
- **User raises the limit above current spend after breach**: The progress bar drops below 100%. No new 80% alert fires retroactively because the handler only checks at the time of each `TransactionCategorized` event.

## Success Outcome
User understands why the alert fired, can see the transactions responsible, and takes action (adjust budget, re-categorise, or accept). The notification is resolved.
