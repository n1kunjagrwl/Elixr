# transactions — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The transactions domain is the single source of truth for every financial movement the user has recorded. From the user's perspective it provides one place to see all debits, credits, and transfers — whether they came from an uploaded bank statement, a CSV import, or a manual entry. Users can add transactions they know will never appear in a statement (e.g., a cash payment), correct the category of any imported transaction after the fact, split a single transaction across multiple categories (e.g., an Amazon order that contains both electronics and groceries), and add notes for personal context. The domain silently protects the user from accidentally double-importing data via fingerprint deduplication, and labels recurring charges and self-transfers automatically so those movements do not pollute expense or income totals.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `transactions`, `transaction_items`, `outbox` |
| Events published | `TransactionCreated`, `TransactionCategorized`, `TransactionUpdated` |
| Events consumed | `ExtractionCompleted` (statements), `ExtractionPartiallyCompleted` (statements), `ImportBatchReady` (import_) |
| Temporal workflows | `RecurringTransactionDetectionWorkflow` (weekly, Sunday 02:00 IST); Transfer Detection scan (post-import) |
| SQL views exposed | `transactions_with_categories` (consumed by earnings, budgets) |
| Slices covered | 15, 16, 44 |

---

## Test Scenarios

---

### Scenario 1: Add a Simple Manual Transaction (single category, no split)

**Source slice**: `docs/slices/15-add-transaction-manually.md`
**Business intent**: A user logs a cash or UPI transaction that did not appear in any uploaded statement.
**Domains involved**: transactions, categorization, earnings, investments, budgets

#### Preconditions
- User is authenticated.
- At least one active bank account or credit card exists for this user.
- At least one active expense category exists in `categories_for_user`.
- No existing transaction with the same description, amount, and date exists for this user (clean fingerprint).

#### Steps
1. `POST /api/v1/transactions/` with `source = 'manual'`, a valid `account_id`, `type = 'debit'`, `amount = 500`, `currency = 'INR'`, `date = today`, `raw_description = 'Swiggy order'`, `notes = null`, and one item: `[{category_id: <food-category-id>, amount: 500, label: null, is_primary: true}]`.

#### Assertions
- **API response**: `201 Created`; response body contains the new transaction `id`, `source = 'manual'`, `fingerprint` is non-null.
- **DB — transactions**: One new row with `user_id`, `account_id`, `amount = 500`, `type = 'debit'`, `source = 'manual'`, `raw_description = 'Swiggy order'`, `fingerprint = SHA-256('swiggy order' + today.isoformat() + '500')`.
- **DB — transaction_items**: Exactly one row linked to the new transaction: `category_id = <food-category-id>`, `amount = 500`, `label = null`, `is_primary = true`.
- **DB — outbox**: Two rows for this transaction — one for `TransactionCreated` and one for `TransactionCategorized`. Both have `user_id` set and are in `pending` state (or processed, depending on poller timing).
- **Events**: After outbox poller runs, `TransactionCreated` is dispatched with `type = 'debit'`, `source = 'manual'`; `TransactionCategorized` is dispatched with `items` list containing the single item.
- **Side effects**: `budgets` handler for `TransactionCategorized` increments `budget_progress.current_spend` for any active budget goal whose `category_id` matches the food category and whose period contains today. `investments` handler for `TransactionCreated` checks against SIP registrations (no match expected here). `earnings` handler skips (type is debit, not credit).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `amount = 0` | `400 Bad Request`; transaction not created; no DB rows inserted | [ ] |
| `amount` is negative | `400 Bad Request` | [ ] |
| `account_id` does not belong to this user | `403 Forbidden` or `422 Unprocessable Entity` | [ ] |
| `account_id` references an inactive account | `422 Unprocessable Entity` — TODO: confirm whether inactive accounts are blocked at API level or only filtered in UI | [ ] |
| Missing required field (`amount`) | `422 Unprocessable Entity` | [ ] |
| Category does not exist | `422 Unprocessable Entity` | [ ] |

---

### Scenario 2: Add a Manual Transaction with Split Items (multiple categories)

**Source slice**: `docs/slices/15-add-transaction-manually.md`
**Business intent**: A user splits an Amazon order across Electronics and Groceries so each budget category receives only its portion.
**Domains involved**: transactions, categorization, budgets

#### Preconditions
- User is authenticated.
- At least one active account exists.
- Two distinct active categories exist (e.g., Shopping and Groceries).
- No duplicate fingerprint for description "Amazon", amount 2000, today's date.

#### Steps
1. `POST /api/v1/transactions/` with `type = 'debit'`, `amount = 2000`, `raw_description = 'Amazon'`, and two items: `[{category_id: <shopping-id>, amount: 1200, label: 'Headphones', is_primary: true}, {category_id: <groceries-id>, amount: 800, label: 'Olive oil', is_primary: false}]`.

#### Assertions
- **API response**: `201 Created`.
- **DB — transactions**: One row, `amount = 2000`, `source = 'manual'`.
- **DB — transaction_items**: Two rows linked to the transaction. Row 1: `category_id = <shopping-id>`, `amount = 1200`, `label = 'Headphones'`, `is_primary = true`. Row 2: `category_id = <groceries-id>`, `amount = 800`, `label = 'Olive oil'`, `is_primary = false`.
- **DB — outbox**: `TransactionCategorized` event payload contains both items with their respective `category_id`, `amount`, `currency`, and `label`.
- **Events**: `TransactionCategorized` dispatched with two-item payload; budgets handler increments `budget_progress.current_spend` for both the Shopping and Groceries budget goals (if they exist for this period) independently.
- **Side effects**: Each category's budget goal is updated by its own item amount, not the full transaction amount.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Items sum to less than transaction total (e.g., items sum 1900, total 2000) | `422 Unprocessable Entity`; validation error message referencing amount mismatch | [ ] |
| Items sum to more than transaction total | `422 Unprocessable Entity` | [ ] |
| Only one item but `is_primary = false` | TODO: clarify whether API enforces that exactly one item must have `is_primary = true` | [ ] |
| Duplicate `category_id` across two items (same category, different labels) | TODO: confirm whether this is allowed (same-category item breakdown, as shown in Scenario B of domain docs) | [ ] |

---

### Scenario 3: Fingerprint Deduplication on Manual Entry

**Source slice**: `docs/slices/15-add-transaction-manually.md`
**Business intent**: Prevent a user from accidentally logging the same transaction twice.
**Domains involved**: transactions

#### Preconditions
- A transaction already exists for this user with `raw_description = 'Swiggy'`, `amount = 500`, `date = 2026-05-10` and fingerprint `SHA-256('swiggy' + '2026-05-10' + '500')`.

#### Steps
1. `POST /api/v1/transactions/` with `raw_description = '  Swiggy  '` (leading/trailing spaces), `amount = 500`, `date = 2026-05-10` (same date), and a valid item.
2. Observe API response — the system must compute fingerprint as `SHA-256(lower(trim('  Swiggy  ')) + '2026-05-10' + '500')`, which equals the existing fingerprint.

#### Assertions
- **API response**: The API must detect the duplicate fingerprint. Expected: either a `409 Conflict` response indicating a duplicate, or a `200 OK` / `201 Created` with a warning flag in the response body indicating a potential duplicate — TODO: confirm which contract the API uses (slice 15 says "user is warned, they may proceed or cancel", suggesting the API may allow proceeding, but does not specify the HTTP status for the warning path).
- **DB**: No new `transactions` row if the API returns 409. If the API returns a warning and the user proceeds (second call with a `force = true` flag or similar), a second row IS inserted with the same fingerprint values — TODO: confirm whether `UNIQUE(user_id, fingerprint)` is a hard DB constraint (which would block even a forced duplicate) or only enforced at the service layer.
- **Events**: No events published for a blocked duplicate. If proceeding after warning, events are published normally.
- **Side effects**: No budget or earnings update for a blocked attempt.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Description with mixed casing (e.g., `SWIGGY` vs `swiggy`) | Both produce the same fingerprint; duplicate is detected | [ ] |
| Description with internal whitespace differences (e.g., `Swiggy  Order` vs `swiggy order`) | `trim` only removes leading/trailing spaces; internal spaces are preserved in the hash; these produce different fingerprints and are not considered duplicates | [ ] |
| Same description and date, different amount | Different fingerprint; no duplicate; transaction created | [ ] |
| Null description on both transactions | Fingerprint is `SHA-256('' + date + amount)`; duplicate detected if date and amount also match | [ ] |

---

### Scenario 4: Add Manual Credit Transaction (income/peer repayment classification)

**Source slice**: `docs/slices/15-add-transaction-manually.md`
**Business intent**: When a user logs a credit transaction manually, downstream domains classify whether it is income or a peer repayment.
**Domains involved**: transactions, earnings, budgets

#### Preconditions
- User is authenticated with at least one active account.
- An active income category exists (e.g., Salary).

#### Steps
1. `POST /api/v1/transactions/` with `type = 'credit'`, `amount = 50000`, `raw_description = 'NEFT from Employer'`, and one item: `[{category_id: <salary-category-id>, amount: 50000, is_primary: true}]`.

#### Assertions
- **API response**: `201 Created`.
- **DB — transactions**: `type = 'credit'`, `source = 'manual'`.
- **DB — transaction_items**: One row, `category_id = <salary-category-id>`, `amount = 50000`, `is_primary = true`.
- **Events**: `TransactionCreated` with `type = 'credit'` published via outbox; `TransactionCategorized` published with items payload.
- **Side effects**: `earnings` domain handler receives `TransactionCreated` (credit); applies heuristics to classify as income or peer repayment; may publish `EarningClassificationNeeded`. `budgets` domain skips credit transactions unless the budget goal targets an income category — TODO: confirm budget handling for credit type.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Credit transaction with an expense category selected | TODO: slice 15 says only income categories are shown for credit type in the UI; confirm whether the API enforces this constraint server-side or only in the UI | [ ] |
| `earnings` handler publishes `EarningClassificationNeeded` | A notification is created for the user via the notifications domain | [ ] |

---

### Scenario 5: Add Manual Transfer Transaction

**Source slice**: `docs/slices/15-add-transaction-manually.md`
**Business intent**: A transfer between the user's own accounts should be excluded from expense and income totals.
**Domains involved**: transactions, categorization, budgets, earnings

#### Preconditions
- User is authenticated.
- "Self Transfer" category (kind = 'transfer') exists in the system.

#### Steps
1. `POST /api/v1/transactions/` with `type = 'transfer'`, `amount = 10000`, `raw_description = 'Transfer to savings'`.
2. Confirm the system assigns the "Self Transfer" category automatically (no category picker interaction required).

#### Assertions
- **API response**: `201 Created`.
- **DB — transactions**: `type = 'transfer'`.
- **DB — transaction_items**: One row with the "Self Transfer" category, `amount = 10000`, `is_primary = true`.
- **Events**: `TransactionCreated` published with `type = 'transfer'`; `TransactionCategorized` published.
- **Side effects**: `budgets` handler checks `type == 'transfer'` at entry and skips entirely — no `budget_progress` rows modified. `earnings` handler similarly skips. No budget alert fired.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User submits a transfer type but also manually supplies a non-transfer category_id | TODO: confirm whether the API overrides the provided category with "Self Transfer" or rejects the inconsistent payload | [ ] |

---

### Scenario 6: Edit Transaction — Re-categorise (retroactive budget correction)

**Source slice**: `docs/slices/16-edit-transaction.md`
**Business intent**: Correcting a transaction's category retroactively adjusts the budget progress for the period in which the transaction occurred.
**Domains involved**: transactions, budgets, categorization

#### Preconditions
- A transaction exists for this user with `type = 'debit'`, `amount = 1000`, `date = 2026-05-01`, categorised as Food & Dining.
- A budget goal exists for Food & Dining for May 2026 with `current_spend` already reflecting the ₹1,000.
- A budget goal exists for Shopping for May 2026.

#### Steps
1. `GET /api/v1/transactions/{transaction_id}` — verify the transaction details and current items.
2. `PATCH /api/v1/transactions/{transaction_id}` with updated items: change the single item from Food & Dining to Shopping, `amount = 1000`, `is_primary = true`.

#### Assertions
- **API response**: `200 OK`.
- **DB — transactions**: `updated_at` is refreshed. `source` is unchanged (retains its original value, e.g., `'manual'` or `'statement_import'`).
- **DB — transaction_items**: Old item row(s) are deleted. New item row exists: `category_id = <shopping-id>`, `amount = 1000`, `is_primary = true`.
- **DB — outbox**: `TransactionUpdated` event row with `changed_fields = ['items']`, `old_items = [{category_id: <food-id>, amount: 1000, ...}]`, `new_items = [{category_id: <shopping-id>, amount: 1000, ...}]`, `date = '2026-05-01'`.
- **Events**: After poller, `TransactionUpdated` dispatched; budgets handler decrements Food & Dining `budget_progress.current_spend` by 1000 (floor at 0), increments Shopping `budget_progress.current_spend` by 1000 for the May 2026 period.
- **Side effects**: If either budget goal has a threshold that the change crosses (e.g., Shopping is now over 80%), an alert fires.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Re-categorisation of a transaction from a prior period (e.g., April 2026) | Budgets handler resolves the period for `event.date = '2026-04-XX'` and adjusts the April budget goal, not the current period | [ ] |
| Old item's budget goal `current_spend` would go negative after decrement | `current_spend` is floored at 0; no negative values stored | [ ] |
| Editing a statement-imported transaction | `200 OK`; `source` field remains `'statement_import'`; all other assertions hold | [ ] |
| Editing a recurring-detected transaction | `200 OK`; `source` remains `'recurring_detected'`; all other assertions hold | [ ] |
| Items updated but new amounts don't sum to transaction total | `422 Unprocessable Entity` | [ ] |

---

### Scenario 7: Edit Transaction — Change Notes Only (no budget recalculation)

**Source slice**: `docs/slices/16-edit-transaction.md`
**Business intent**: Editing only notes does not trigger any downstream budget recalculation.
**Domains involved**: transactions, budgets

#### Preconditions
- A transaction exists with an existing note (or null note).

#### Steps
1. `PATCH /api/v1/transactions/{transaction_id}` with `notes = 'reimbursable from company'` and no change to items.

#### Assertions
- **API response**: `200 OK`.
- **DB — transactions**: `notes = 'reimbursable from company'`, `updated_at` refreshed.
- **DB — transaction_items**: Unchanged.
- **DB — outbox**: `TransactionUpdated` with `changed_fields = ['notes']`, `old_items = null`, `new_items = null`.
- **Events**: `TransactionUpdated` dispatched; budgets handler sees `'items'` is NOT in `changed_fields` and skips entirely.
- **Side effects**: No `budget_progress` rows modified. No alerts fired.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Setting notes to empty string | TODO: confirm whether empty string is stored or coerced to null | [ ] |
| Simultaneous notes and items change in one request | `changed_fields = ['notes', 'items']`; budgets handler processes the items diff; both fields updated atomically | [ ] |

---

### Scenario 8: Edit Transaction — Change Type to Transfer

**Source slice**: `docs/slices/16-edit-transaction.md`
**Business intent**: Marking a transaction as a transfer excludes it from both expense budgets and income classification.
**Domains involved**: transactions, budgets, earnings

#### Preconditions
- A debit transaction exists, categorised as Food & Dining, with a matching budget goal.

#### Steps
1. `PATCH /api/v1/transactions/{transaction_id}` changing `type` from `'debit'` to `'transfer'`.

#### Assertions
- **API response**: `200 OK`.
- **DB — transactions**: `type = 'transfer'`.
- **DB — transaction_items**: Items replaced with a single "Self Transfer" category item.
- **DB — outbox**: `TransactionUpdated` with `changed_fields = ['type']` (and `['items']` if the category was also replaced — TODO: confirm whether the auto-assignment of Self Transfer category counts as an items change in `changed_fields`).
- **Events**: `TransactionUpdated` dispatched; budgets handler checks `type == 'transfer'` and skips; earnings handler skips.
- **Side effects**: No `budget_progress` rows modified. The previous Food & Dining spend is NOT decremented — TODO: confirm whether a type-to-transfer edit also triggers old-items budget correction, or whether that is only done when `'items'` is explicitly in `changed_fields`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Changing type from transfer back to debit | New items must be provided; budgets re-applies; earnings re-classifies if now credit | [ ] |

---

### Scenario 9: Transactions Created from Statement Import (ExtractionCompleted event)

**Source slice**: `docs/domains/transactions.md — Events Subscribed`
**Business intent**: When the statements workflow finishes processing an uploaded statement, the transactions domain creates all transaction and item records automatically from the classified rows payload.
**Domains involved**: transactions, statements, budgets, earnings, investments

#### Preconditions
- A statement processing job has completed.
- `ExtractionCompleted` event is present in the outbox (published by the statements domain) with a `classified_rows` payload containing at least 3 rows of varying types (debit, credit, transfer).
- No prior transactions exist for this user with the same fingerprints as the classified rows (clean slate).

#### Steps
1. Simulate (or wait for) the outbox poller to dispatch `ExtractionCompleted` to the transactions domain event handler.
2. The handler creates one `transactions` row and one or more `transaction_items` rows per classified row in the payload.
3. For each created transaction, `TransactionCreated` and `TransactionCategorized` are published to the outbox.

#### Assertions
- **API response**: Not directly applicable (event-driven). Assert via `GET /api/v1/transactions/` that the new rows are visible.
- **DB — transactions**: N new rows (one per classified row), all with `source = 'statement_import'`. This value is set because the handler was triggered by `statements.ExtractionCompleted` (or `statements.ExtractionPartiallyCompleted`); contrast with `source = 'bulk_import'` which is set when the handler is triggered by `import_.ImportBatchReady` (see Scenario 10).
- **DB — transaction_items**: At least N rows (one per transaction at minimum); split transactions may produce more.
- **DB — outbox**: `TransactionCreated` and `TransactionCategorized` published for each newly created transaction.
- **Events**: Downstream handlers receive events: budgets updates `budget_progress`, earnings classifies credits, investments checks debits against SIP registrations.
- **Side effects**: Transfer detection scan runs post-import; if any debit and credit share the same amount, currency, user, different accounts, and close dates, both are updated to `type = 'transfer'` and assigned the "Self Transfer" category. An SSE notification is emitted to the user.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `ExtractionCompleted` contains a row whose fingerprint already exists for this user | Handler skips that row (idempotent); no duplicate transaction created | [ ] |
| Same `ExtractionCompleted` event dispatched twice (at-least-once delivery) | All rows on second dispatch have existing fingerprints; all rows skipped; no duplicates | [ ] |
| `ExtractionPartiallyCompleted` event (timeout path) | Same handler logic; only `classified_rows` are processed; unclassified rows are absent from the payload and not created | [ ] |
| Classified row has `type = 'transfer'` already set by the workflow | Transaction created with `type = 'transfer'`; Self Transfer category assigned; transfer detection scan skips it | [ ] |
| Transfer detection matches a newly imported debit with a pre-existing credit from a prior import | Both transactions updated to `type = 'transfer'`; SSE notification emitted | [ ] |

---

### Scenario 10: Transactions Created from CSV Bulk Import (ImportBatchReady event)

**Source slice**: `docs/domains/transactions.md` — Events Subscribed
**Business intent**: Historical data imported via CSV creates transaction records with `source = 'bulk_import'`; re-uploading the same CSV is safe due to fingerprint deduplication.
**Domains involved**: transactions, import_

#### Preconditions
- An import job has completed; `ImportBatchReady` is in the outbox with rows formatted identically to `ExtractionCompleted.classified_rows`.
- At least one row in the payload has a fingerprint that already exists (simulating a re-upload scenario).

#### Steps
1. Outbox poller dispatches `ImportBatchReady` to the transactions handler.

#### Assertions
- **DB — transactions**: Only rows with new fingerprints are created. Rows with existing fingerprints are skipped.
- **DB — transactions**: All newly created rows have `source = 'bulk_import'`. This value is set because the handler was triggered by `import_.ImportBatchReady`; contrast with `source = 'statement_import'` which is set when triggered by `statements.ExtractionCompleted` / `statements.ExtractionPartiallyCompleted` (see Scenario 9).
- **DB — transaction_items**: Items created per new transaction.
- **Events**: `TransactionCreated` and `TransactionCategorized` published for each inserted transaction. No events for skipped rows.
- **Side effects**: Same downstream processing as Scenario 9 (budgets, earnings, investments).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| All rows in the batch are duplicates | Zero new rows created; no events published; no error returned | [ ] |
| Entire batch of 1000 rows with zero duplicates | All 1000 rows created atomically; if the handler fails mid-batch, no partial rows committed | [ ] |

---

### Scenario 11: Browse Transactions — Default List (no filters)

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: A user opening the transaction list sees all their transactions in reverse chronological order, with account and primary category resolved.
**Domains involved**: transactions, accounts (user_accounts_summary view), categorization (categories_for_user view)

#### Preconditions
- User is authenticated.
- At least 3 transactions exist across 2 different accounts with different categories.
- All transactions have at least one `transaction_items` row with `is_primary = true`.

#### Steps
1. `GET /api/v1/transactions/` (no query parameters).

#### Assertions
- **API response**: `200 OK`; list of transactions ordered by `date DESC`, then `created_at DESC`.
- **API response — each row includes**: `id`, `date`, `amount`, `currency`, `type`, `source`, `raw_description`, `notes`, account name and kind (resolved from `user_accounts_summary` view, NOT from `bank_accounts` or `credit_cards` directly), primary category name and icon (from the `transaction_items` row where `is_primary = true`, resolved via `categories_for_user` view).
- **API response**: No transactions from other users are included.
- **DB**: Query joins `user_accounts_summary` for account name, not `bank_accounts`/`credit_cards` directly (assert via query plan or integration test asserting the view is used).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Transaction has no `transaction_items` (uncategorised) | Row is still returned in the list; primary category displayed as "Uncategorised" | [ ] |
| Transaction's account is deactivated | Row is still returned; account name shown as "Deactivated account" (sourced from `user_accounts_summary.is_active`) | [ ] |
| User has zero transactions | `200 OK` with empty list; empty state handled without 404 | [ ] |

---

### Scenario 12: Browse Transactions — Cursor-Based Pagination

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: Large transaction histories load efficiently without missing or duplicating rows when new transactions arrive between pages.
**Domains involved**: transactions

#### Preconditions
- User has at least 110 transactions (to exercise at least 3 pages with page size 50).
- All transactions have distinct dates.

#### Steps
1. `GET /api/v1/transactions/` — first page (default: `page=1`, `page_size=50`); note total rows and page metadata from the response.
2. `GET /api/v1/transactions/?page=2` — second page.
3. `GET /api/v1/transactions/?page=3` — third page (partial).
4. Between step 1 and step 2, insert a new transaction with a date newer than all existing transactions.

#### Assertions
- **API response — page 1**: 50 rows (default `page_size=50`); response includes pagination metadata (current page, page size, total count or has-next indicator).
- **API response — page 2**: 50 rows; no overlap with page 1; no gap (no row skipped).
- **API response — page 3**: 10 remaining rows; response indicates end of results.
- **New transaction inserted between pages**: May appear on page 1 of a fresh request; offset-based pagination does not guarantee stability when new rows are inserted at the front — TODO: confirm whether the API uses strict offset or a stable keyset/cursor under the hood.
- **Total row count across all pages**: Exactly 110 original rows accessible across pages 1–3.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Two transactions have identical `date` (same date, different IDs) | Ordered by `date DESC, created_at DESC`; consistent ordering across pages | [ ] |
| `page` param beyond last page (e.g., `page=99` when only 3 pages exist) | `200 OK` with empty list; no error | [ ] |
| Page size parameter provided | `page_size` is configurable via query param; default is 50, maximum is 100. Requests with `page_size > 100` should be rejected with a `422 Unprocessable Entity`. | [ ] |

---

### Scenario 13: Browse Transactions — Filter by Account

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: A user can narrow the transaction list to one or more specific accounts.
**Domains involved**: transactions, accounts

#### Preconditions
- User has transactions across at least 2 accounts (e.g., account A: 10 transactions, account B: 5 transactions).

#### Steps
1. `GET /api/v1/transactions/?account_id=<account-A-id>` — filter by account A only.

#### Assertions
- **API response**: Only transactions belonging to account A are returned (10 rows); account B transactions are absent.
- **API response**: Query uses `WHERE account_id IN (:selected_ids) AND account_kind IN (:selected_kinds)`.
- **API response**: Page resets to page 1 when filter is applied.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Filter by multiple accounts simultaneously | All transactions for any of the selected accounts are returned | [ ] |
| Filter by an `account_id` that belongs to a different user | `403 Forbidden` or empty result (no cross-user data leak) | [ ] |
| Filter by an inactive account | Transactions for that account are returned (deactivated accounts are not purged) | [ ] |

---

### Scenario 14: Browse Transactions — Filter by Category

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: Filtering by category lets a user see all spending in a chosen category, including split transactions that only partially belong to that category.
**Domains involved**: transactions, categorization

#### Preconditions
- User has: 3 transactions purely in Food & Dining; 1 split transaction with one item in Food & Dining and one item in Shopping.

#### Steps
1. `GET /api/v1/transactions/?category_id=<food-category-id>` — filter by Food & Dining.

#### Assertions
- **API response**: 4 transactions returned (the 3 pure + 1 split); the split transaction appears once, not twice.
- **API response**: The list view shows the primary category badge (`is_primary = true` item) for each row.
- **DB**: Query joins `transaction_items` and filters `WHERE ti.category_id IN (:selected_category_ids)`; deduplication ensures the split transaction appears only once.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Filter by category that matches only non-primary items of a split | Transaction still appears in results (the join does not restrict to `is_primary = true`) | [ ] |
| Filter by `type = credit` AND `category = Food & Dining` (incompatible combination) | Empty list returned; no error; empty state shown to user | [ ] |
| Transaction with no items (uncategorised) | Does NOT appear when filtering by any category (requires a matching `transaction_items` row) | [ ] |

---

### Scenario 15: Browse Transactions — Filter by Date Range

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: Date range filtering lets the user review spending for a specific period.
**Domains involved**: transactions

#### Preconditions
- Transactions exist spanning at least 3 months.

#### Steps
1. `GET /api/v1/transactions/?date_from=2026-05-01&date_to=2026-05-31` — This Month filter.
2. `GET /api/v1/transactions/?date_from=2026-04-01&date_to=2026-04-30` — Last Month filter.

#### Assertions
- **API response — step 1**: Only transactions with `date >= 2026-05-01 AND date <= 2026-05-31`.
- **API response — step 2**: Only transactions with `date >= 2026-04-01 AND date <= 2026-04-30`.
- **API response**: Filters are additive with other active filters (e.g., date range + account filter combines correctly).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `date_from > date_to` | `422 Unprocessable Entity` | [ ] |
| Date range spanning "This Year" with thousands of transactions | First page returns promptly; subsequent pages load on demand via `page` param | [ ] |
| Transaction with `date = date_from` exactly | Included (boundary is inclusive) | [ ] |
| Transaction with `date = date_to` exactly | Included (boundary is inclusive) | [ ] |

---

### Scenario 16: Browse Transactions — Filter by Type and Source

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: Type and source filters allow audit-style queries (e.g., "show me only manually entered transactions" or "show me only debits").
**Domains involved**: transactions

#### Preconditions
- Transactions exist with all four source values: `manual`, `statement_import`, `bulk_import`, `recurring_detected`.
- Transactions exist with all three type values: `debit`, `credit`, `transfer`.

#### Steps
1. `GET /api/v1/transactions/?type=debit` — only debit transactions.
2. `GET /api/v1/transactions/?source=manual` — only manual transactions.
3. `GET /api/v1/transactions/?type=debit&source=manual` — combined filter.

#### Assertions
- **API response — step 1**: All returned rows have `type = 'debit'`; no credit or transfer rows.
- **API response — step 2**: All returned rows have `source = 'manual'`; no imported or recurring rows.
- **API response — step 3**: All returned rows have `type = 'debit'` AND `source = 'manual'`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Filter by multiple types simultaneously (`type=debit,credit`) | Returns all debit and credit transactions; transfers excluded | [ ] |
| Filter by `source = recurring_detected` | Only transactions where `source = 'recurring_detected'`; these will display a "Recurring" badge | [ ] |

---

### Scenario 17: Browse Transactions — Keyword Search

**Source slice**: `docs/slices/44-browse-search-transactions.md`
**Business intent**: A user can search by a keyword to find transactions from a specific merchant or category without navigating filters.
**Domains involved**: transactions

#### Preconditions
- Transactions exist with `raw_description` values including "Swiggy Order", "SWIGGY ONLINE", "Netflix Monthly", "Rent Payment".

#### Steps
1. `GET /api/v1/transactions/?search_text=swiggy` — case-insensitive keyword search.
2. `GET /api/v1/transactions/?search_text=swiggy&type=debit` — keyword combined with type filter.
3. `GET /api/v1/transactions/?search_text=a` — single character (below minimum length).

#### Assertions
- **API response — step 1**: Returns rows with `raw_description ILIKE '%swiggy%'`; matches "Swiggy Order" and "SWIGGY ONLINE"; does NOT search in `notes`, category names, or item labels.
- **API response — step 2**: Returns rows matching both the keyword and `type = 'debit'`.
- **API response — step 3**: `400 Bad Request` or empty result; TODO: confirm whether the minimum 2-character constraint is enforced at the API level or only in the UI.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Search term matches thousands of transactions | Result is paginated; first page returns promptly; TODO: confirm whether a result count cap applies | [ ] |
| Search term with special SQL characters (e.g., `%`, `_`) | Safely escaped; no SQL injection; literal `%` treated as a character to search for, not a wildcard | [ ] |
| Search term matches `notes` or `label` but not `raw_description` | NOT returned (search is on `raw_description` only) | [ ] |

---

### Scenario 18: Transaction Detail View

**Source slice**: `docs/slices/44-browse-search-transactions.md` — Step 10
**Business intent**: Tapping a transaction shows its full details including all split items, account, source badge, and peer settlement linkage.
**Domains involved**: transactions, accounts, categorization

#### Preconditions
- A split transaction exists with 2 items, notes set, and `source = 'statement_import'`.
- A `peer_settlements` row exists that references this transaction's `id`.

#### Steps
1. `GET /api/v1/transactions/{transaction_id}`.

#### Assertions
- **API response**: `200 OK`; response includes `raw_description`, `date`, `amount`, `currency`, `type`, `source`, account name and kind (from `user_accounts_summary`), all `transaction_items` (both items, each with `category_id`, `category_name`, `category_icon`, `label`, `amount`), `notes`, and a `linked_peer_settlement` flag or reference.
- **API response**: `source = 'statement_import'` is present; UI can render a source badge.
- **API response**: Accessing another user's transaction `id` returns `403 Forbidden` or `404 Not Found` (no cross-user data leak).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `source = 'recurring_detected'` | Response includes the detected recurrence pattern; UI renders a "Recurring" badge | [ ] |
| `source = 'bulk_import'` | Response includes source badge | [ ] |
| Transaction has no linked peer settlement | `linked_peer_settlement = null`; no indicator shown | [ ] |
| Transaction ID does not exist | `404 Not Found` | [ ] |

---

## Known Inconsistencies

- **[1.2] Transaction deletion** — `docs/business-intent/transactions.md` (section "What It Does Not Do") explicitly states: "Does not delete transactions. Once a transaction exists it can only be edited, not removed (to preserve ledger integrity)." However, `docs/slices/26-budget-alert-response.md` (edge cases) references "user deleted a transaction after the alert" as a valid scenario. This is a direct contradiction. **Test implication**: do not write a test for a DELETE endpoint; no such endpoint should exist. Confirmed: the API exposes no `DELETE /api/v1/transactions/{transaction_id}` route. If a DELETE endpoint is discovered during testing, that is a bug. The slice 26 edge case should be revised to read "user re-categorised a transaction to a different category."

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| `RecurringTransactionDetectionWorkflow` — no E2E scenario covers the weekly scan labelling transactions as `source = 'recurring_detected'` | `docs/domains/transactions.md` — Temporal Workflows | Write a workflow integration test that seeds 90 days of debit transactions for the same merchant at a monthly interval, triggers the workflow, and asserts `source = 'recurring_detected'` is set on those rows |
| Transfer detection post-import scan — no dedicated scenario covers the case where the counterpart transaction comes from a prior import (not the same job) | `docs/domains/transactions.md` — Transfer Detection | Extend Scenario 9 edge case or add a separate scenario seeding a pre-existing credit before the import runs |
| `GET /api/v1/transactions/{transaction_id}` contract not fully specified — the exact shape of the detail response (especially how items are nested and whether `categories_for_user` view is used) | `docs/slices/44-browse-search-transactions.md` — Step 10 | Confirm API response schema with backend; update Scenario 18 assertions once contract is finalised |
| Duplicate fingerprint warning flow — the exact HTTP contract (409 vs. 200 with warning flag, and whether a `force` parameter allows proceeding) is not specified in the slice | `docs/slices/15-add-transaction-manually.md` — Step 3 | Clarify and document the API contract; update Scenario 3 assertions |
| Minimum keyword search length enforcement — whether the 2-character minimum is API-enforced or UI-only is not specified | `docs/slices/44-browse-search-transactions.md` — Step 8 | Confirm with backend; if API-enforced, update Scenario 17 step 3 expected response |
| `TransactionCategorized` vs `TransactionUpdated` — when items are replaced on an edit, is `TransactionCategorized` also re-published, or only `TransactionUpdated`? | `docs/domains/transactions.md` — Events Published | Confirm with domain implementation; affects budget handler test assertions |
| No test scenario for `GET /api/v1/transactions/` security: ensure user A cannot query user B's transactions by guessing IDs | Cross-cutting | Add auth isolation test asserting 403/404 for cross-user transaction IDs |
| `ExtractionPartiallyCompleted` handler — dedicated test confirming that unclassified rows (absent from payload) are never created | `docs/domains/transactions.md` — Events Subscribed | Extend Scenario 9 edge cases or add a dedicated scenario |

---

## TODO

- [ ] Confirm whether inactive accounts are blocked at the API level when creating a transaction (Scenario 1 edge case).
- [ ] Confirm whether the API enforces that exactly one item must have `is_primary = true`, or whether that is a service-layer default.
- [ ] Confirm whether same-category multi-item splits (Scenario B from domain docs) are allowed via API, and whether any uniqueness constraint on `(transaction_id, category_id)` exists.
- [ ] Confirm the HTTP contract for the duplicate fingerprint warning path (409 vs. warning flag + force parameter).
- [ ] Confirm whether `UNIQUE(user_id, fingerprint)` is a hard DB constraint or only a service-layer check; this determines whether a "force proceed" on a duplicate is even possible.
- [ ] Confirm whether the type-to-transfer edit also emits `changed_fields = ['items']` alongside `['type']` when the category is auto-changed to Self Transfer, and whether that triggers a budget old-items decrement.
- [ ] Confirm budget handler behaviour for credit-type transactions (whether credit categories can have budget goals).
- [ ] Confirm whether API enforces income-only categories for credit-type transactions at the server side.
- [x] ~~Confirm page size: fixed at 50 or configurable via query param~~ ✅ Resolved: `page_size` query param is supported; default is 50, maximum is 100. Updated Scenario 12 edge case accordingly.
- [ ] Confirm whether a result count cap applies to keyword search results.
- [ ] Confirm whether the API uses strict offset pagination or a stable keyset/cursor under the hood; confirm behaviour when `page` is beyond the last page (empty list vs. 422); confirm exact pagination metadata shape in the response envelope.
- [ ] Add E2E tests for the `RecurringTransactionDetectionWorkflow` once the workflow is deployed.
- [ ] Review slice 26 and update its edge case to remove the reference to transaction deletion.
