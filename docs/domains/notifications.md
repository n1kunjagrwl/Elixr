# Domain: notifications

## Responsibility

Generates and stores in-app notification banners for the user. This domain is a pure consumer — it subscribes to events from across the system and converts them into user-facing notifications. It never originates events and has no business logic of its own beyond mapping an event to a notification message and deep-link.

Notifications are in-app only. No SMS, no email, no push notifications at this stage.

---

## Tables Owned

### `notifications`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `type` | `text` NOT NULL | Event type that created this notification (used for grouping/filtering) |
| `title` | `text` NOT NULL | Short heading e.g. "Budget limit reached" |
| `body` | `text` NOT NULL | Detail e.g. "You've spent ₹4,200 of your ₹4,000 Food & Dining budget this month." |
| `metadata` | `jsonb` | Deep-link data for frontend navigation e.g. `{"route": "/budgets/goal/{id}"}` |
| `read_at` | `timestamptz` NULLABLE | NULL = unread |
| `created_at` | `timestamptz` | — |

No `outbox` table — the notifications domain only consumes events and writes to its own table. It does not publish events.

---

## SQL Views Exposed

None.

---

## Events Published

None.

---

## Events Subscribed

### `BudgetLimitWarning` (from `budgets`)
Creates a notification:
- Title: `"Approaching budget limit"`
- Body: `"You've used {percent}% of your {category} budget (₹{spent} of ₹{limit}) this {period}."`
- Metadata: `{"route": "/budgets", "goal_id": "{goal_id}"}`

### `BudgetLimitBreached` (from `budgets`)
Creates a notification:
- Title: `"Budget limit exceeded"`
- Body: `"You've exceeded your {category} budget by ₹{overage}. Spent ₹{spent} against a ₹{limit} limit."`
- Metadata: `{"route": "/budgets", "goal_id": "{goal_id}"}`

### `SIPDetected` (from `investments`)
Creates a notification asking for confirmation:
- Title: `"SIP payment detected"`
- Body: `"We noticed a ₹{amount} debit that looks like your {instrument_name} SIP. Tap to confirm."`
- Metadata: `{"route": "/investments/sip/confirm", "transaction_id": "{tx_id}", "sip_id": "{sip_id}"}`

### `ExtractionCompleted` (from `statements`)
Creates a notification confirming the statement has been processed:
- Title: `"Statement processed"`
- Body: `"{n} transactions from your {account_name} statement are ready to review."`
- Metadata: `{"route": "/statements/{job_id}/review"}`

### `EarningClassificationNeeded` (from `earnings`)
Creates a notification asking the user to classify an ambiguous credit:
- Title: `"New credit to classify"`
- Body: `"A ₹{amount} credit arrived — is this income or a repayment from someone? Tap to classify."`
- Metadata: `{"route": "/earnings/classify", "transaction_id": "{tx_id}"}`

### `AccountLinked` (from `accounts`)
Creates an onboarding nudge when the user adds a new account:
- Title: `"Account added"`
- Body: `"Upload a statement or log a transaction to start tracking {nickname}."`
- Metadata: `{"route": "/statements/upload", "account_id": "{account_id}"}`

### `ExtractionPartiallyCompleted` (from `statements`)
Creates a warning when a statement timed out with unclassified rows:
- Title: `"Statement partially imported"`
- Body: `"{n} transactions were saved. Rows from {discarded_from_date} to {discarded_to_date} were not classified and have been discarded. Upload the statement again to process the remaining rows — duplicates will be skipped automatically."`
- Metadata: `{"route": "/statements/upload", "account_id": "{account_id}"}`

### `ImportCompleted` (from `import_`)
Creates a completion notification when a bulk import finishes:
- Title: `"Import complete"`
- Body: `"{imported_rows} transactions imported. {skipped_rows} duplicates skipped."`
- Metadata: `{"route": "/transactions", "job_id": "{job_id}"}`

---

## Service Methods Exposed

None.

---

## Key Design Decisions

**`metadata` as JSONB for deep-link routing.** The frontend reads `metadata.route` to navigate the user to the relevant screen when they tap a notification. Storing this as JSONB means new notification types can carry arbitrary navigation context without a schema change.

**No delivery mechanism beyond in-app storage.** Notifications are written to the DB and the frontend polls `GET /notifications?unread=true`. This is deliberately simple. Push notifications, email, and SMS can be added later by adding a delivery worker that reads from this table and dispatches via the appropriate channel — the data model already supports it.

**Idempotency per handler.** Each handler guards against duplicate notifications caused by at-least-once event delivery. The guard key varies by notification type:
- `BudgetLimitWarning` / `BudgetLimitBreached`: check for an existing notification with matching `type`, `metadata->>'goal_id'`, and `metadata->>'period_start'` before inserting.
- `SIPDetected`: check for existing notification with `type = 'SIPDetected'` and `metadata->>'transaction_id'` + `metadata->>'sip_id'` pair.
- `EarningClassificationNeeded`: check for existing notification with `type` and `metadata->>'transaction_id'`.
- `ExtractionCompleted` / `ExtractionPartiallyCompleted`: check for existing notification with `type` and `metadata->>'job_id'`.
- `AccountLinked` / `ImportCompleted`: check for existing notification with `type` and `metadata->>'account_id'` or `metadata->>'job_id'` respectively.
If a matching notification already exists, skip insertion — do not create a duplicate.

**No deduplication at this layer beyond idempotency.** The events that trigger notifications are already deduplicated at their source (e.g., `budgets` ensures only one breach alert per goal per period). The idempotency check above handles re-delivery of the same event; it does not suppress intentional repeated events (e.g., a second SIP on a different date).

**Notifications are never deleted, only marked read.** This gives the user a notification history. The `read_at` column is set on explicit user action (`PATCH /notifications/{id}/read` or bulk `PATCH /notifications/read-all`). Old notifications can be archived (hidden from feed after 90 days) without deletion.
