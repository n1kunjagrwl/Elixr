# notifications — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The notifications domain exists so that users of Elixir never have to actively poll each screen to find out what has happened since their last visit. Elixir processes statements, tracks budgets, detects SIP payments, and flags ambiguous credits all in the background; without a notification layer the user would miss these events entirely. The domain surfaces them as an in-app feed of actionable banners — each with a deep link to the affected screen — so the user opens the app, sees exactly what needs attention, taps a notification to act on it, and marks it read once done. Notifications are never deleted, only marked read, giving the user a permanent history of every alert the system has ever raised.

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `notifications` |
| Events published | None |
| Events consumed | `BudgetLimitWarning` (budgets), `BudgetLimitBreached` (budgets), `SIPDetected` (investments), `ExtractionCompleted` (statements), `ExtractionPartiallyCompleted` (statements), `EarningClassificationNeeded` (earnings), `AccountLinked` (accounts), `ImportCompleted` (import_) |
| Temporal workflows | None |
| Slices covered | 36, 37 |

## Test Scenarios

---

### Scenario 1: View unread notification inbox

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: User opens the notification bell and sees all unread notifications ordered newest-first, each with the correct title, body, and unread indicator.
**Domains involved**: notifications

#### Preconditions
- Authenticated user exists.
- At least one `notifications` row exists for this user with `read_at IS NULL`.
- At least one `notifications` row exists for this user with `read_at IS NOT NULL` (to verify unread filter works).

#### Steps
1. Authenticate as the test user and obtain a valid session token.
2. Call `GET /api/v1/notifications/?unread=true`.
3. Inspect the response body.

#### Assertions
- **API response**: HTTP 200.
- **API response**: Every returned notification has `read_at: null`.
- **API response**: Notifications are ordered by `created_at` descending.
- **API response**: Each notification object includes `id`, `type`, `title`, `body`, `metadata`, `read_at`, and `created_at` fields.
- **API response**: Notifications with `read_at IS NOT NULL` in the DB are NOT present in the response.
- **DB**: `SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND read_at IS NULL` matches the count in the response.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| No unread notifications exist | HTTP 200 with empty array `[]`; UI should show "All caught up" empty state | [ ] |
| User has only read notifications | `GET /api/v1/notifications/?unread=true` returns `[]` | [ ] |
| Notifications older than 90 days | Hidden from feed response (not deleted from DB) — `created_at < now() - interval '90 days'` rows are excluded | [ ] |
| `GET /api/v1/notifications/` (no filter) | Returns all notifications including read ones; 90-day cutoff still applies | [ ] |
| Unauthenticated request | HTTP 401 | [ ] |
| Request for another user's notifications | HTTP 403 or empty result — `user_id` filter enforced | [ ] |

---

### Scenario 2: Notification deep-link metadata is correct per type

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: Each notification type carries `metadata.route` so the frontend can navigate the user directly to the relevant screen when tapped.
**Domains involved**: notifications

#### Preconditions
- One notification of each type has been created for the test user.

#### Steps
1. Call `GET /api/v1/notifications/` as the test user.
2. For each notification type, inspect the `metadata` field.

#### Assertions
- **API response**: `BudgetLimitWarning` and `BudgetLimitBreached` notifications contain `metadata.route = "/budgets"` and `metadata.goal_id`.
- **API response**: `SIPDetected` notifications contain `metadata.route = "/investments/sip/confirm"`, `metadata.transaction_id`, and `metadata.sip_id`.
- **DB**: For `SIPDetected` notifications: `metadata->>'sip_id' IS NOT NULL` — `sip_id` is always present in the `SIPDetected` event payload and must be persisted in the notification metadata.
- **API response**: `ExtractionCompleted` notifications contain `metadata.route = "/statements/{job_id}/review"`.
- **API response**: `ExtractionPartiallyCompleted` notifications contain `metadata.route = "/statements/upload"` and `metadata.account_id`.
- **API response**: `EarningClassificationNeeded` notifications contain `metadata.route = "/earnings/classify"` and `metadata.transaction_id`.
- **API response**: `AccountLinked` notifications contain `metadata.route = "/statements/upload"` and `metadata.account_id`.
- **API response**: `ImportCompleted` notifications contain `metadata.route = "/transactions"` and `metadata.job_id`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Deep-link destination is stale (e.g., statement already completed on another device) | Frontend navigates to destination; destination screen handles stale state gracefully (e.g., "Statement already processed") | [ ] |

---

### Scenario 3: BudgetLimitWarning event creates a notification

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When a user's spending reaches 80% of a category budget limit, the system raises a warning notification so the user can adjust spending before going over.
**Domains involved**: notifications, budgets

#### Preconditions
- Authenticated user with a `budget_goals` row for a category (e.g., Food & Dining, limit ₹5,000 for the current period).
- A transaction is added that pushes spend to >= 80% of the limit (e.g., ₹4,100 spent, 82%).
- The `budgets` domain publishes a `BudgetLimitWarning` event to the outbox.

#### Steps
1. Trigger the event by inserting a `BudgetLimitWarning` outbox entry (or via the API path that causes the budgets domain to publish it).
2. Wait for the outbox poller to dispatch the event (up to 5 seconds / 3 polling cycles).
3. Call `GET /api/v1/notifications/?unread=true` as the test user.

#### Assertions
- **DB**: One `notifications` row exists with `type = 'BudgetLimitWarning'`, `user_id = :uid`, and `metadata->>'goal_id' = :goal_id`.
- **DB**: `read_at IS NULL`.
- **API response**: The notification appears in the unread feed.
- **API response**: `title = "Approaching budget limit"`.
- **API response**: `body` contains the spend percentage, category name, spent amount, and limit amount.
- **API response**: `metadata.route = "/budgets"` and `metadata.goal_id` matches the budget goal.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same `BudgetLimitWarning` event delivered twice (at-least-once delivery) | Only one notification row created — idempotency guard on `(type, goal_id, period_start)` | [ ] |
| Two different budget goals both breach 80% | Two separate `BudgetLimitWarning` notifications created, one per goal | [ ] |

---

### Scenario 4: BudgetLimitBreached event creates a notification

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When spending exceeds 100% of a budget limit, the user is alerted so they can review the overspend.
**Domains involved**: notifications, budgets

#### Preconditions
- Authenticated user with a `budget_goals` row.
- A transaction pushes spend over 100% of the limit.
- The `budgets` domain publishes a `BudgetLimitBreached` event.

#### Steps
1. Trigger the `BudgetLimitBreached` event via the budgets domain outbox.
2. Wait for the outbox poller to dispatch.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'BudgetLimitBreached'`, correct `user_id`, and `metadata->>'goal_id'`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "Budget limit exceeded"`.
- **API response**: `body` includes the overage amount, spent amount, and limit amount in INR.
- **API response**: `metadata.goal_id` matches the breached goal.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Multiple transactions push the same goal over the limit in rapid succession | Only one `BudgetLimitBreached` notification per goal per period — deduplication at the `budgets` domain level; notifications domain idempotency guard provides a second layer | [ ] |
| `BudgetLimitBreached` event re-delivered | Idempotency guard on `(type, goal_id, period_start)` prevents duplicate row | [ ] |

---

### Scenario 5: SIPDetected event creates a confirmation notification

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When a debit matches a registered SIP, the user is prompted to confirm the payment so investment records stay accurate.
**Domains involved**: notifications, investments

#### Preconditions
- Authenticated user with a registered SIP (`sip_registrations` row).
- A transaction matching the SIP amount triggers a `SIPDetected` event in the investments domain.

#### Steps
1. Publish a `SIPDetected` event with `transaction_id` and `sip_id` via the investments outbox.
2. Wait for outbox poller.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'SIPDetected'`, `metadata->>'transaction_id' = :tx_id`, and `metadata->>'sip_id' = :sip_id`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "SIP payment detected"`.
- **API response**: `body` contains the debit amount and instrument name.
- **API response**: `metadata.route = "/investments/sip/confirm"`.
- **API response**: `metadata.transaction_id` and `metadata.sip_id` are present.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same `SIPDetected` event delivered twice | Idempotency guard on `(type, transaction_id, sip_id)` — only one notification created | [ ] |
| Two separate SIP payments detected on the same day (different `transaction_id`) | Two separate `SIPDetected` notifications created | [ ] |

---

### Scenario 6: ExtractionCompleted event creates a statement-ready notification

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: After a statement is fully processed, the user is notified that their transactions are ready to review.
**Domains involved**: notifications, statements

#### Preconditions
- Authenticated user has an extraction job that transitions to `completed`.
- The `statements` domain publishes an `ExtractionCompleted` event with `job_id`, `account_name`, and transaction count.

#### Steps
1. Publish an `ExtractionCompleted` event via the statements outbox.
2. Wait for outbox poller.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'ExtractionCompleted'` and `metadata->>'job_id' = :job_id`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "Statement processed"`.
- **API response**: `body` contains the transaction count and account name.
- **API response**: `metadata.route` includes `"/statements/{job_id}/review"`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same `ExtractionCompleted` event delivered twice | Idempotency guard on `(type, job_id)` — single notification | [ ] |

---

### Scenario 7: ExtractionPartiallyCompleted event creates a partial-import warning

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When a statement import times out and discards some rows, the user is warned and prompted to re-upload to recover those transactions.
**Domains involved**: notifications, statements

#### Preconditions
- A statement extraction job times out before all rows are classified, producing an `ExtractionPartiallyCompleted` event with `n`, `discarded_from_date`, `discarded_to_date`, and `account_id`.

#### Steps
1. Publish an `ExtractionPartiallyCompleted` event.
2. Wait for outbox poller.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'ExtractionPartiallyCompleted'` and `metadata->>'job_id' = :job_id`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "Statement partially imported"`.
- **API response**: `body` contains the saved row count, discarded date range, and the instruction to re-upload (with duplicate-skip assurance).
- **API response**: `metadata.route = "/statements/upload"` and `metadata.account_id` is present.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same partial-completion event delivered twice | Idempotency guard on `(type, job_id)` prevents duplicate | [ ] |

---

### Scenario 8: EarningClassificationNeeded event creates a classification prompt

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When a credit cannot be automatically classified as income or a peer repayment, the user is prompted to classify it so earnings records stay accurate.
**Domains involved**: notifications, earnings

#### Preconditions
- A transaction credit triggers an `EarningClassificationNeeded` event in the earnings domain with `transaction_id` and `amount`.

#### Steps
1. Publish an `EarningClassificationNeeded` event.
2. Wait for outbox poller.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'EarningClassificationNeeded'` and `metadata->>'transaction_id' = :tx_id`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "New credit to classify"`.
- **API response**: `body` contains the credit amount.
- **API response**: `metadata.route = "/earnings/classify"` and `metadata.transaction_id` is present.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same event delivered twice | Idempotency guard on `(type, transaction_id)` prevents duplicate | [ ] |

---

### Scenario 9: AccountLinked event creates an onboarding nudge

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When a user adds a new bank account or credit card, they are nudged to upload a statement or log a transaction so the account is immediately useful.
**Domains involved**: notifications, accounts

#### Preconditions
- User adds a new account, causing the `accounts` domain to publish an `AccountLinked` event with `account_id` and `nickname`.

#### Steps
1. Publish an `AccountLinked` event.
2. Wait for outbox poller.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'AccountLinked'` and `metadata->>'account_id' = :account_id`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "Account added"`.
- **API response**: `body` contains the account nickname and instruction to upload or log.
- **API response**: `metadata.route = "/statements/upload"` and `metadata.account_id` is present.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same `AccountLinked` event delivered twice | Idempotency guard on `(type, account_id)` prevents duplicate | [ ] |

---

### Scenario 10: ImportCompleted event creates a bulk-import completion notification

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: When a CSV bulk import finishes, the user is informed how many transactions were imported and how many were skipped as duplicates.
**Domains involved**: notifications, import_

#### Preconditions
- A bulk import job completes, and the `import_` domain publishes an `ImportCompleted` event with `job_id`, `imported_rows`, and `skipped_rows`.

#### Steps
1. Publish an `ImportCompleted` event.
2. Wait for outbox poller.
3. Call `GET /api/v1/notifications/?unread=true`.

#### Assertions
- **DB**: One `notifications` row with `type = 'ImportCompleted'` and `metadata->>'job_id' = :job_id`.
- **DB**: `read_at IS NULL`.
- **API response**: `title = "Import complete"`.
- **API response**: `body` contains `imported_rows` and `skipped_rows` counts.
- **API response**: `metadata.route = "/transactions"` and `metadata.job_id` is present.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Same `ImportCompleted` event delivered twice | Idempotency guard on `(type, job_id)` prevents duplicate | [ ] |

---

### Scenario 11: Mark single notification as read on tap

**Source slice**: `docs/slices/37-mark-notifications-read.md`
**Business intent**: Tapping a notification marks it read and navigates the user to the relevant screen, clearing the unread indicator.
**Domains involved**: notifications

#### Preconditions
- Authenticated user has at least one notification with `read_at IS NULL`.

#### Steps
1. Obtain the `id` of an unread notification via `GET /api/v1/notifications/?unread=true`.
2. Call `PATCH /api/v1/notifications/{id}/read`.
3. Call `GET /api/v1/notifications/?unread=true` again.
4. Query the DB directly for the notification row.

#### Assertions
- **DB**: `SELECT read_at FROM notifications WHERE id = :id` — `read_at IS NOT NULL`.
- **DB**: `read_at` value is a recent timestamp (within a few seconds of the PATCH call).
- **API response** (step 2): HTTP 200 with body `{"ok": true}`.
- **API response** (step 3): The marked notification no longer appears in the unread feed.
- **Events**: No events published — this is a read-only state change within the notifications domain.
- **Side effects**: No other domain tables are affected by this call.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `PATCH /api/v1/notifications/{id}/read` called on a notification that is already read | HTTP 200 `{"ok": true}` (idempotent); `read_at` timestamp unchanged or updated to now — confirm idempotency behaviour TODO | [ ] |
| `PATCH /api/v1/notifications/{id}/read` called on a notification belonging to a different user | HTTP 403 or 404 | [ ] |
| `PATCH /api/v1/notifications/{id}/read` called with an invalid UUID | HTTP 422 | [ ] |
| `PATCH /api/v1/notifications/{id}/read` called on a non-existent notification ID | HTTP 404 | [ ] |

---

### Scenario 12: Mark all notifications as read

**Source slice**: `docs/slices/37-mark-notifications-read.md`
**Business intent**: The user can clear all unread notifications in one tap, bringing the badge count to zero.
**Domains involved**: notifications

#### Preconditions
- Authenticated user has at least three notifications with `read_at IS NULL`.

#### Steps
1. Confirm unread count via `GET /api/v1/notifications/?unread=true` — note the count.
2. Call `PATCH /api/v1/notifications/read-all`.
3. Call `GET /api/v1/notifications/?unread=true`.
4. Query the DB directly.

#### Assertions
- **DB**: `SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND read_at IS NULL` returns 0.
- **DB**: All previously-unread rows now have `read_at IS NOT NULL`.
- **API response** (step 2): HTTP 200 with body `{"updated": N}` where N is the number of rows marked read.
- **API response** (step 3): Empty array `[]`.
- **Events**: No events published.
- **Side effects**: Notifications are still present in DB and visible via `GET /api/v1/notifications/` (no filter); they are not deleted.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Concurrent `PATCH /api/v1/notifications/read-all` from two devices | Both succeed; second call is a no-op for already-read rows; no conflict | [ ] |
| New notification arrives between the read-all call and the next fetch | New notification has `read_at IS NULL`; badge reappears with count 1; this is expected behaviour | [ ] |
| No unread notifications exist when read-all is called | HTTP 200 `{"updated": 0}`; no rows affected; response is still success | [ ] |
| Unauthenticated request | HTTP 401 | [ ] |

---

### Scenario 13: Unread badge count reflects DB state

**Source slice**: `docs/slices/36-view-notifications.md`
**Business intent**: The notification bell badge count must accurately reflect the number of unread notifications so the user knows when to check the inbox.
**Domains involved**: notifications

#### Preconditions
- Authenticated user has exactly N notifications with `read_at IS NULL` (use a known seed value, e.g., N=3).

#### Steps
1. Call `GET /api/v1/notifications/unread-count` — confirm `{"count": N}`.
2. Call `GET /api/v1/notifications/?unread=true` — count the items in the response array.
3. Mark one as read via `PATCH /api/v1/notifications/{id}/read`.
4. Call `GET /api/v1/notifications/?unread=true` again.
5. Call `GET /api/v1/notifications/unread-count` again.

#### Assertions
- **API response** (step 1): `{"count": N}` (e.g., `{"count": 3}`).
- **API response** (step 2): Response array length equals N (3).
- **DB**: `SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND read_at IS NULL` equals N.
- **API response** (step 4): Response array length equals N-1 (2).
- **API response** (step 5): `{"count": N-1}` (e.g., `{"count": 2}`).
- **DB**: Count decremented to N-1 after the PATCH.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User has notifications from multiple domains | All unread notifications appear in a single feed regardless of type | [ ] |

---

### Scenario 14: Notification history preserved after mark-all-read

**Source slice**: `docs/slices/37-mark-notifications-read.md`
**Business intent**: Marking notifications as read does not delete them; the user can still browse notification history.
**Domains involved**: notifications

#### Preconditions
- User has notifications with `read_at IS NULL`.

#### Steps
1. Call `PATCH /api/v1/notifications/read-all`.
2. Call `GET /api/v1/notifications/` (no `unread=true` filter).
3. Check the DB.

#### Assertions
- **API response** (step 2): HTTP 200 with the same notifications that were previously unread now shown with `read_at` populated.
- **DB**: All notification rows are still present; `COUNT(*)` matches pre-read-all count.
- **DB**: No rows were deleted.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Notifications older than 90 days | Not returned in the feed but still present in DB | [ ] |

---

## Known Inconsistencies

### [1.4] Statement resume notification — no backing event for workflow-paused-mid-classification state

`docs/slices/11-resume-abandoned-statement.md` states that the slice trigger is a notification "Statement partially classified — tap to continue". However, `docs/domains/notifications.md` lists 8 subscribed events and none of them fire when a `StatementProcessingWorkflow` pauses in the `awaiting_input` state (i.e., when the user closes the app mid-classification).

The `ExtractionPartiallyCompleted` event fires only on **timeout**, not on browser close. A user who abandons classification without a timeout receives no notification and must discover the in-progress statement by navigating to the Statements screen manually.

**Testing impact**: Scenario 7 above tests `ExtractionPartiallyCompleted` (timeout path only). There is currently no testable path for the "paused mid-classification" notification described in slice 11. Any test that attempts to verify this trigger will fail because the backing event does not exist. A test should be added once a `ClassificationAbandoned` event (or equivalent) is defined and implemented.

---

### [1.5] SIP registration deactivation notification — no handler in notifications domain

`docs/slices/29-register-sip.md` edge cases state: "Bank account removed after registration: … A notification informs the user that the SIP registration was deactivated." However, `docs/domains/notifications.md` has no handler for any `AccountRemoved` or SIP-deactivation event. The investments domain publishes only `SIPDetected`, `SIPLinked`, and `ValuationUpdated` — none of which cover deactivation.

**Testing impact**: There is no testable path for this notification. If a test is written to verify that removing a bank account triggers a notification about SIP deactivation, it will fail. The notification is silently absent. A test should be added once the `investments` domain publishes a `SIPRegistrationDeactivated` event and the notifications domain adds a corresponding handler.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| `ClassificationAbandoned` event (workflow paused mid-classification) | `docs/domains/notifications.md` — Known Gaps; `docs/business-intent/INCONSISTENCIES.md` [1.4] | Define the event, add a handler in the notifications domain, then add a Scenario for the resume notification in this guide |
| `SIPRegistrationDeactivated` event (SIP silently deactivated when account is removed) | `docs/domains/notifications.md` — Known Gaps; `docs/business-intent/INCONSISTENCIES.md` [1.5] | Have `investments` domain publish the event when a SIP registration is deactivated, add a handler, then add a Scenario here |
| No notification on `SIPLinked` (user confirmed a detected SIP) | `docs/domains/notifications.md` — events subscribed list does not include `SIPLinked` | Confirm whether a confirmation notification is desired; if yes, add handler and scenario |
| No notification on `ValuationUpdated` (scheduled investment revaluation) | `docs/domains/notifications.md` — events subscribed list does not include `ValuationUpdated` | Out of scope per current design (informational-only periodic event); confirm and document the decision |

## TODO

- Confirm idempotency behaviour for `PATCH /api/v1/notifications/{id}/read` when called on an already-read notification: does `read_at` stay unchanged (first-write-wins) or update to now (last-write-wins)? Document the chosen behaviour and add a concrete assertion to Scenario 11.
- Confirm the 90-day archival cutoff: is it enforced at the query level (API excludes old rows) or at a scheduled cleanup job? Identify the mechanism and add a DB-level assertion to the edge case in Scenario 1.
- Confirm whether `GET /api/v1/notifications/` (no filter) also applies the 90-day cutoff or returns the full history. The slice implies old notifications are hidden from the "feed" but accessible in an "archived view" — the exact API shape is not documented.
- Confirm default `page_size` for `GET /api/v1/notifications/` is 20 in all pagination assertions (default confirmed from source: `page_size=20`).
- Add Playwright E2E tests for the frontend notification bell badge: verify the badge count decrements when `PATCH /api/v1/notifications/{id}/read` succeeds, and drops to zero after `PATCH /api/v1/notifications/read-all`.
- Verify that `user_id` isolation is enforced at both the application layer and PostgreSQL RLS for all notification endpoints.
