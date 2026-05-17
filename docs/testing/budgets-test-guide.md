# budgets — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The budgets domain lets users commit to category-level spending limits over a chosen time period (calendar month, salary-aligned month, week, or custom range) and then tracks actual spend automatically as transactions flow in. The user never has to manually update their progress — each time a relevant transaction is categorised, the running total is updated in the background and the user is proactively alerted at the 80% and 100% thresholds. Budgets are advisory and informational only: they do not block spending, do not backfill pre-creation transactions, and apply only to expense categories. The goal is to give users a real-time picture of whether they are on track, with enough notice to change behaviour before a limit is crossed.

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `budget_goals`, `budget_progress`, `budget_alerts`, `outbox` |
| Events published | `budgets.BudgetLimitWarning` (80% threshold), `budgets.BudgetLimitBreached` (100% threshold) |
| Events consumed | `TransactionCategorized` (from `transactions`), `TransactionUpdated` (from `transactions`) |
| Temporal workflows | None — the domain is purely event-driven |
| Slices covered | 24, 25, 26, 42 |

## Test Scenarios

---

### Scenario 1: Create a budget goal for an expense category

**Source slice**: `docs/slices/24-create-budget.md`
**Business intent**: A user sets a monthly spending limit on an expense category and the system immediately begins tracking spend from zero.
**Domains involved**: budgets, categorization, fx

#### Preconditions
- User is authenticated.
- At least one category with `kind = 'expense'` and `is_active = true` exists for this user (e.g., "Food & Dining").

#### Steps
1. `GET /categories?kind=expense&is_active=true` — verify the category picker returns only expense categories.
2. `POST /api/v1/budgets/` with body: `{ "category_id": "<food-category-id>", "limit_amount": 5000, "currency": "INR", "period_type": "monthly" }`.
3. Record the returned `goal_id` and `progress_id`.

#### Assertions
- **API response**: HTTP 201. Body contains `goal_id`, `is_active: true`, `period_type: "monthly"`, `limit_amount: 5000`, `currency: "INR"`.
- **DB (`budget_goals`)**: One row with `user_id`, `category_id`, `limit_amount = 5000`, `currency = 'INR'`, `period_type = 'monthly'`, `is_active = true`, `period_anchor_day IS NULL`.
- **DB (`budget_progress`)**: One row with `goal_id`, `user_id`, `current_spend = 0.00`, `period_start` = first day of the current calendar month, `period_end` = last day of the current calendar month.
- **Events**: No event is published at creation time. Confirm the `outbox` table has no new rows for this `goal_id`.
- **Side effects**: None. The domain is now in a passive-reactive state, waiting for `TransactionCategorized` events.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `category_id` references an income or transfer category | API returns 422 Unprocessable Entity | [ ] |
| `limit_amount = 0` | API returns 422 — amount must be > 0 | [ ] |
| `limit_amount` is negative | API returns 422 | [ ] |
| `period_type = "custom"` with `custom_end` before `custom_start` | API returns 422 — `custom_end` must be > `custom_start` | [ ] |
| `period_type = "monthly"` with `period_anchor_day = 31` | API returns 422 — maximum is 28 | [ ] |
| `period_type = "monthly"` with `period_anchor_day = 28` | Accepted; period runs 28th of this month to 27th of next month | [ ] |
| Duplicate budget: same `category_id` + same `period_type` for the same user | Accepted (HTTP 201) — both goals track independently, each with its own `budget_progress` row | [ ] |
| Income or transfer-type category shown in picker | Category picker should not include `kind != 'expense'` entries | [ ] |

---

### Scenario 2: Budget created mid-period — no backfill of prior transactions

**Source slice**: `docs/slices/24-create-budget.md`
**Business intent**: A budget created partway through a period starts from zero and does not retroactively count transactions that were already imported before the budget existed.
**Domains involved**: budgets, transactions

#### Preconditions
- User is authenticated.
- At least one categorised `expense` transaction in the current calendar month already exists for the "Food & Dining" category (imported before this test).
- The user has no existing budget goal for "Food & Dining".

#### Steps
1. Verify that a "Food & Dining" transaction dated within the current month exists in the DB with a non-zero `amount`.
2. `POST /api/v1/budgets/` with `category_id` = Food & Dining, `limit_amount = 5000`, `period_type = "monthly"`.
3. `GET /api/v1/budgets/{goal_id}` (budget detail endpoint).

#### Assertions
- **DB (`budget_progress`)**: `current_spend = 0.00` immediately after creation, despite pre-existing transactions in the same category and period.
- **API response**: `current_spend = 0`, `percent_used = 0.0`.
- **Events**: No event published.
- **Side effects**: The existing transactions in the ledger are not touched. Their own records are unchanged.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Transaction dated in a prior month exists for same category | Still not backfilled — `current_spend` remains 0 | [ ] |
| First `TransactionCategorized` event arrives after budget creation | `current_spend` is updated; pre-creation spend remains excluded | [ ] |

---

### Scenario 3: Event-driven spend tracking — `TransactionCategorized` updates `budget_progress`

**Source slice**: `docs/slices/24-create-budget.md` (Step 5), `docs/slices/25-view-budget-status.md`
**Business intent**: Every time a relevant expense transaction is categorised, the matching budget's running total is automatically incremented without any user action.
**Domains involved**: budgets, transactions, fx

#### Preconditions
- User is authenticated.
- An active `budget_goals` row exists for "Food & Dining" with `limit_amount = 5000`, `period_type = "monthly"`, `current_spend = 0`.
- The current date falls within the budget's period.

#### Steps
1. Create a new transaction for "Food & Dining" dated today with `amount = 1000, currency = "INR"`.
2. Trigger (or wait for) the `TransactionCategorized` event to be dispatched by the outbox poller.
3. `GET /api/v1/budgets/{goal_id}`.

#### Assertions
- **DB (`budget_progress`)**: `current_spend = 1000.00` after the event is processed.
- **DB (`budget_alerts`)**: No alert row yet (20% used; below both thresholds).
- **API response**: `current_spend = 1000`, `limit_amount = 5000`, `percent_used ≈ 0.20`.
- **Events**: No `BudgetLimitWarning` or `BudgetLimitBreached` published.
- **Side effects**: `budget_progress.updated_at` is refreshed.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Transaction `type = 'transfer'` is categorised | Handler skips — `current_spend` unchanged | [ ] |
| Transaction `currency` differs from goal `currency` (e.g., USD transaction, INR budget) | `fx.convert()` is called; converted INR amount is added to `current_spend` | [ ] |
| Transaction date falls outside the current period (e.g., dated last month) | Handler skips — `current_spend` unchanged, no `budget_progress` row created for that past period | [ ] |
| Same `TransactionCategorized` event replayed (at-least-once delivery) | `current_spend` is not double-incremented — handler is idempotent | [ ] |
| Transaction has multiple line items; only one item matches the budget category | Only the matching item's amount is added to `current_spend` | [ ] |

---

### Scenario 4: 80% warning alert threshold crossing

**Source slice**: `docs/slices/24-create-budget.md` (Step 5), `docs/slices/26-budget-alert-response.md`
**Business intent**: When cumulative spend in the budget period crosses 80% of the limit, exactly one warning notification is fired and deduplicated for the rest of the period.
**Domains involved**: budgets, notifications

#### Preconditions
- Active `budget_goals` row: `limit_amount = 5000`, `period_type = "monthly"`, `current_spend = 3900` (78% used — just below threshold).
- No `budget_alerts` row for this goal + current period.

#### Steps
1. Create a new "Food & Dining" expense transaction of `amount = 200` (pushing total to 4100 — 82%).
2. Trigger `TransactionCategorized` event dispatch.
3. Query `budget_alerts` for this `goal_id` and current `period_start`.
4. Query `notifications` table for this user.

#### Assertions
- **DB (`budget_progress`)**: `current_spend = 4100.00`.
- **DB (`budget_alerts`)**: One row with `goal_id`, `threshold_percent = 80`, `current_spend = 4100`, `period_start` matching current period.
- **Events**: `budgets.BudgetLimitWarning` published to the outbox with `percent_used` between 0.80 and 0.99, correct `goal_id`, `user_id`, `category_id`, `period_start`, `period_end`.
- **API response** (dashboard): `percent_used ≈ 0.82`, visual state is `warning` (amber).
- **Side effects**: `notifications` domain creates a notification row with title "Approaching budget limit" and deep-link `{"route": "/budgets", "goal_id": "<id>"}`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| A second `TransactionCategorized` event arrives when spend is already above 80% | No second `BudgetLimitWarning` published — `budget_alerts` deduplication prevents it | [ ] |
| `BudgetLimitWarning` event is replayed (at-least-once delivery) | Handler checks `budget_alerts` before publishing — duplicate notification is suppressed | [ ] |
| Spend crosses 80% and 100% in a single transaction | Both `BudgetLimitWarning` and `BudgetLimitBreached` fire; both `budget_alerts` rows inserted | [ ] |

---

### Scenario 5: 100% breach alert threshold crossing

**Source slice**: `docs/slices/24-create-budget.md` (Step 5), `docs/slices/26-budget-alert-response.md`
**Business intent**: When spend reaches or exceeds the budget limit, exactly one breach notification is fired per period with the overage amount clearly stated.
**Domains involved**: budgets, notifications

#### Preconditions
- Active `budget_goals` row: `limit_amount = 5000`, `current_spend = 4800` (96% used).
- A `budget_alerts` row with `threshold_percent = 80` already exists for this goal + period (80% alert already fired).
- No `budget_alerts` row with `threshold_percent = 100` for this goal + period.

#### Steps
1. Create a "Food & Dining" expense transaction of `amount = 300` (pushing total to 5100 — 102%).
2. Trigger `TransactionCategorized` event dispatch.
3. Query `budget_alerts` for this `goal_id` and current `period_start`.
4. Query `notifications` table for this user.

#### Assertions
- **DB (`budget_progress`)**: `current_spend = 5100.00`.
- **DB (`budget_alerts`)**: A new row with `threshold_percent = 100`, `current_spend = 5100`. The prior 80% row is unchanged.
- **Events**: `budgets.BudgetLimitBreached` published with `current_spend = 5100`, `limit_amount = 5000`, correct `goal_id`.
- **API response** (dashboard): `percent_used ≈ 1.02`, visual state is `breached` (red), overage text shows "₹100 over limit".
- **Side effects**: `notifications` domain creates a notification row with title "Budget limit exceeded" and correct overage amount.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Two 100% alerts attempted in the same period | Second alert is suppressed — only one `threshold_percent = 100` row per goal per period | [ ] |
| User raises `limit_amount` above current spend after breach | Progress bar drops below 100%; no new 80% alert fires retroactively (alerts only fire on new event processing) | [ ] |
| User reduces `limit_amount` so that existing spend already exceeds the new limit | Breach alert fires only on the next qualifying `TransactionCategorized` event, not retroactively | [ ] |

---

### Scenario 6: View budget status dashboard

**Source slice**: `docs/slices/25-view-budget-status.md`
**Business intent**: The budget dashboard shows every active goal's spend vs. limit for the current period as a fast, pre-computed lookup — not a live aggregation.
**Domains involved**: budgets, categorization

#### Preconditions
- User has at least two active `budget_goals` rows: one under 80%, one over 100%.
- Both have `budget_progress` rows covering today's date.

#### Steps
1. `GET /api/v1/budgets/` (budget list / dashboard endpoint).
2. `GET /api/v1/budgets/{goal_id}` for the detail view of the over-budget goal.

#### Assertions
- **API response (list)**: Returns both goals. Each entry includes `category_name`, `category_icon`, `limit_amount`, `current_spend`, `period_start`, `period_end`, `percent_used`.
- **API response (list)**: Under-80% goal has a `status` of `neutral` (or equivalent). Over-100% goal has a `status` of `breached`.
- **API response (detail)**: Shows the current period's transactions list filtered by `category_id` and the period date range (via `transactions_with_categories` view). Shows `budget_alerts` history for this goal.
- **DB**: No additional queries touch the `transactions` table directly — only the view.
- **Side effects**: None. This is a read-only operation.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Goal `is_active = false` | Excluded from dashboard results | [ ] |
| No `budget_progress` row exists for the current period (budget created for a future custom period) | TODO: clarify whether the endpoint omits the goal or returns it with `current_spend = 0` | [ ] |
| `current_spend = 0` (no transactions yet this period) | Progress bar shows 0%, `percent_used = 0.0` — valid state | [ ] |
| Multiple active budgets for the same category | Each shown as a separate card with independent progress bars | [ ] |
| User navigates to "Previous period" | API computes prior period's `period_start` / `period_end` from `period_type`; returns `budget_progress` for that period; shows zero-spend placeholder if no row exists | [ ] |

---

### Scenario 7: Retroactive budget correction via `TransactionUpdated`

**Source slice**: `docs/slices/26-budget-alert-response.md` (Step 4B)
**Business intent**: When a user re-categorises a transaction, the affected budget totals are automatically corrected — the old category's progress is decremented and the new category's progress is incremented.
**Domains involved**: budgets, transactions

#### Preconditions
- Active goal A for "Food & Dining", `current_spend = 2000`.
- Active goal B for "Shopping", `current_spend = 500`.
- A transaction dated within the current period has `items` pointing to "Food & Dining" with `amount = 800`.
- No 80% or 100% alerts have fired for either goal.

#### Steps
1. Edit the transaction to change its category from "Food & Dining" to "Shopping".
2. Confirm `TransactionUpdated` event is published with `changed_fields` containing `items`, `old_items`, and `new_items`.
3. Trigger event dispatch.
4. Query `budget_progress` for both goals.

#### Assertions
- **DB (`budget_progress` for goal A)**: `current_spend = 1200` (decremented by 800).
- **DB (`budget_progress` for goal B)**: `current_spend = 1300` (incremented by 800).
- **DB**: `current_spend` never goes below 0 (floor enforced).
- **Events**: Threshold re-check runs for both goals after correction; alerts fire if any threshold is newly crossed.
- **Side effects**: `budget_progress.updated_at` refreshed for both goals.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `TransactionUpdated` event has `changed_fields` without `items` (e.g., only `notes` changed) | Handler skips entirely — no `budget_progress` changes | [ ] |
| Re-categorisation moves transaction to a category with no active budget | Old goal decremented; no increment applied (no matching goal for new category) | [ ] |
| Decrement would push `current_spend` below 0 | `current_spend` is floored at 0 | [ ] |
| `TransactionUpdated` event replayed (at-least-once delivery) | Handler checks whether transaction's current items already match `new_items`; if so, skips to avoid double-correction | [ ] |
| Transaction date outside the budget period | Handler skips; no `budget_progress` row is modified | [ ] |

---

### Scenario 8: Edit a budget goal's limit amount

**Source slice**: `docs/slices/42-edit-deactivate-budget.md`
**Business intent**: A user can raise or lower a budget's spending limit at any time; the new limit takes effect immediately for all future event processing without modifying historical spend totals.
**Domains involved**: budgets

#### Preconditions
- Active `budget_goals` row: `limit_amount = 5000`, `current_spend = 3000`.
- User is authenticated and owns the goal.

#### Steps
1. `PATCH /api/v1/budgets/{goal_id}` with body `{ "limit_amount": 7000 }`.
2. Query `budget_goals` and `budget_progress`.

#### Assertions
- **API response**: HTTP 200. Body includes `limit_amount: 7000`, `updated_at` refreshed.
- **DB (`budget_goals`)**: `limit_amount = 7000`, `updated_at` refreshed.
- **DB (`budget_progress`)**: `current_spend` unchanged at 3000.
- **Events**: No event published.
- **Side effects**: None. The new limit governs the next `TransactionCategorized` event's threshold check.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Attempt to change `category_id` via the edit endpoint | API rejects the change — `category_id` is immutable after creation (returns 422 or ignores the field) | [ ] |
| Attempt to change `currency` via the edit endpoint | API rejects the change — `currency` is immutable after creation | [ ] |
| Reduce `limit_amount` so current spend already exceeds it | Breach alert fires only on the next qualifying `TransactionCategorized` event, not immediately on save | [ ] |
| Edit `period_anchor_day` | Accepted; next `TransactionCategorized` event creates a new `budget_progress` row for the re-computed period; old row remains in history | [ ] |
| Edit `period_type` from `monthly` to `weekly` | Accepted; future events resolve the period using the new type; existing `budget_progress` rows are not modified or deleted | [ ] |
| Edit `custom_start` / `custom_end` to dates that don't include today | Goal disappears from the active dashboard (no `budget_progress` row matches `period_start ≤ today ≤ period_end`) until a new qualifying transaction arrives | [ ] |

---

### Scenario 9: Deactivate a budget goal

**Source slice**: `docs/slices/42-edit-deactivate-budget.md`
**Business intent**: A user can turn off a budget goal they no longer need; the goal stops tracking immediately and disappears from the dashboard, but all historical spend data is preserved.
**Domains involved**: budgets

#### Preconditions
- Active `budget_goals` row: `is_active = true`.
- At least one `budget_progress` row and one `budget_alerts` row exist for this goal.

#### Steps
1. `DELETE /api/v1/budgets/{goal_id}` → `204 No Content` (soft-delete / deactivate).
2. Query `budget_goals`, `budget_progress`, and `budget_alerts`.
3. `GET /api/v1/budgets/` (budget list dashboard).
4. Create a new expense transaction in the deactivated goal's category and trigger event dispatch.

#### Assertions
- **DB (`budget_goals`)**: `is_active = false`, `updated_at` refreshed.
- **DB (`budget_progress`)**: All rows preserved and unchanged.
- **DB (`budget_alerts`)**: All rows preserved and unchanged.
- **API response (dashboard)**: Deactivated goal does not appear in the active goals list.
- **Events**: No event published on deactivation.
- **Side effects**: Subsequent `TransactionCategorized` events for this goal's category are skipped by the handler (checks `is_active` at the top of every event).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `TransactionCategorized` event in-flight at the moment of deactivation | Event may be processed once before `is_active = false` is visible to the handler (accepted race condition under at-least-once delivery); the next event will skip cleanly | [ ] |
| Deactivating a goal that fired a 100% alert this period | Alert rows remain in `budget_alerts`; no notification is sent to the user about the deactivation itself | [ ] |
| Hard-delete attempted via API | Not supported — API should return 405 Method Not Allowed or redirect to deactivation; `budget_progress` history must not be deleted | [ ] |
| Reactivating a deactivated goal | `is_active = true` is set; goal reappears on dashboard; only new transactions (post-reactivation) are tracked — no backfill of transactions that occurred while inactive | [ ] |

---

### Scenario 10: Budget alert deduplication after edit-limit-up following a breach

**Source slice**: `docs/slices/26-budget-alert-response.md` (Step 4A and edge case)
**Business intent**: Alerts that have already fired are not retracted when the user raises the limit; the alert history reflects past states, not the current limit.
**Domains involved**: budgets, notifications

#### Preconditions
- `budget_goals`: `limit_amount = 5000`, `current_spend = 5200`.
- `budget_alerts`: one row `threshold_percent = 80`, one row `threshold_percent = 100` for the current period.

#### Steps
1. `PATCH /api/v1/budgets/{goal_id}` with `{ "limit_amount": 6000 }`.
2. Query `budget_alerts` and `budget_progress`.
3. `GET /api/v1/budgets/` (budget list dashboard).

#### Assertions
- **DB (`budget_goals`)**: `limit_amount = 6000`.
- **DB (`budget_alerts`)**: Both existing alert rows remain. No rows are deleted or retracted.
- **DB (`budget_progress`)**: `current_spend = 5200` unchanged.
- **API response (dashboard)**: `percent_used ≈ 0.867` — goal now shows as `warning` state (amber), not `breached`.
- **Events**: No event published.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| A new transaction arrives after the limit increase, percent drops below 80% | No new 80% alert fires retroactively | [ ] |
| A new transaction arrives after the limit increase, new spend crosses 80% of the raised limit | A new 80% alert fires (new period/threshold combination if 80% alert for prior limit already fired — TODO: clarify deduplication key: is it per period + threshold only, or per period + threshold + limit_amount?) | [ ] |

---

## Known Inconsistencies

The following inconsistencies from `docs/business-intent/INCONSISTENCIES.md` are directly relevant to the budgets domain and must be flagged in testing.

### [1.2] Transaction deletion referenced in slice 26 edge case vs. domain doc

`docs/slices/26-budget-alert-response.md` edge case states: "Alert fired but spend is now under 80% (e.g., **user deleted a transaction** after the alert)". However, `docs/business-intent/transactions.md` explicitly states: "Does not delete transactions. Once a transaction exists it can only be edited, not removed." The scenario where deletion causes spend to fall below an alert threshold is therefore not a real user path. The edge case should read "user re-categorised a transaction to a different category" — the `TransactionUpdated` retroactive handler would then correct `budget_progress`. The alert would remain in the notification feed regardless, as the slice correctly notes.

**Testing implication**: Do not write a test for budget spend correction via transaction deletion. Write the test for re-categorisation only (covered in Scenario 7). If a delete endpoint unexpectedly exists or is added later, it must also publish a `TransactionUpdated`-equivalent event so budget progress is corrected.

### [3.6] Budget tracking does not backfill pre-creation transactions

`docs/business-intent/budgets.md` does not state that a newly created budget starts with `current_spend = 0` regardless of existing transactions. The detail is only present in `docs/slices/24-create-budget.md`. This is a meaningful user-trust issue: a user creating a budget mid-month will see a dashboard that appears to show no spending in categories where spending clearly occurred. The budget numbers are technically correct (they reflect only post-creation activity) but may be confusing.

**Testing implication**: Scenario 2 explicitly covers this. Any test that seeds pre-existing transactions before budget creation must assert `current_spend = 0` immediately after creation, and must not assert that old transactions appear in the budget total.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| Salary-aligned period resolution (`period_anchor_day`) mid-month creation | `slices/24-create-budget.md` Step 3 | Add a test that creates a budget with `period_type = "monthly"` and `period_anchor_day = 15` on a date outside the 15th–14th window; assert correct `period_start` and `period_end` in `budget_progress` |
| Weekly period boundary (Monday–Sunday rollover) | `domains/budgets.md` period resolution logic | Add a test that creates a weekly budget, submits a transaction dated in week N, then another in week N+1; assert two separate `budget_progress` rows |
| Custom period goal with `period_type = "custom"` end-to-end | `slices/24-create-budget.md` Step 3 | Add a test covering creation, spend tracking, and alert within a custom date range |
| Past-period navigation (`budget_progress` lookup for prior period) | `slices/25-view-budget-status.md` Step 4 | Add a test that queries a previous period and asserts correct `period_start`/`period_end` and a zero-spend placeholder when no row exists |
| `rollover` column behaviour | `domains/budgets.md` Key Design Decisions | Marked as reserved for future use; no tests needed yet. Note here for when it is implemented. |
| Notification content validation (exact message body with `{percent}`, `{category}`, `{spent}`, `{limit}`) | `slices/26-budget-alert-response.md` Step 1 | Add assertions in Scenarios 4 and 5 once the notifications domain's test guide defines how notification body is verified |
| Budget detail view: alert history from `budget_alerts` returned in API response | `slices/25-view-budget-status.md` Step 3 | Add a sub-assertion in Scenario 6 detail-view step once API schema for budget detail is confirmed |
| Deactivation API endpoint shape | `slices/42-edit-deactivate-budget.md` | ✅ Resolved: `DELETE /api/v1/budgets/{goal_id}` → `204 No Content` (soft-delete / deactivate). Scenario 9 updated. |

## TODO

- ~~Confirm the exact endpoint shape for deactivation (Scenario 9)~~ ✅ Resolved: `DELETE /api/v1/budgets/{goal_id}` → `204 No Content`. Scenario 9 updated.
- [ ] Confirm deduplication key for `budget_alerts`: is the unique constraint on `(goal_id, period_start, threshold_percent)` exactly? Needed to determine Scenario 10 edge case behaviour when the limit changes between alert firings.
- [ ] Clarify dashboard response when an active goal has no `budget_progress` row for the current period (e.g., a custom-range goal whose window hasn't started yet) — omitted from results, or returned with `current_spend = 0`?
- [ ] Add integration tests for `fx.convert()` path in Scenarios 3 and 7 once the fx domain test guide defines mock FX rate setup.
- [ ] Verify whether `budget_progress` rows for prior periods are accessible through the API (needed for Scenario 6 previous-period navigation test).
- [ ] Once `rollover` is implemented, add scenarios for effective limit calculation (`limit_amount + previous_period_unspent`) and threshold checks against the effective limit.
