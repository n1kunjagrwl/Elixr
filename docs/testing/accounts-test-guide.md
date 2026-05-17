# accounts — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The accounts domain gives users a way to name their bank accounts and credit cards so that transactions and statement uploads have a meaningful, human-readable source. Before a user can upload a statement or log a transaction, they must register an account label (e.g., "HDFC Savings" or "HDFC Millennia"). The domain also carries the metadata — particularly `billing_cycle_day` on credit cards — that other domains such as `budgets` use when aligning period calculations. It does not connect to any bank, track live balances, or store full account numbers; only the last 4 digits are kept. Deactivating an account hides it from the UI while preserving all historical transactions and statements linked to it.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `bank_accounts`, `credit_cards`, `outbox` |
| Events published | `accounts.AccountLinked` (on creation), `accounts.AccountRemoved` (on deactivation or hard-delete) |
| Events consumed | `accounts.AccountLinked` (self-subscription — internal side effect), `accounts.AccountRemoved` (self-subscription — internal side effect) |
| Temporal workflows | None (overlap detection runs inside `statements` domain's `StatementProcessingWorkflow`) |
| SQL views exposed | `user_accounts_summary` (union of `bank_accounts` and `credit_cards`; consumed by `statements`, `transactions`, `investments`) |
| Slices covered | 05, 06, 07, 08 |

---

## Test Scenarios

---

### Scenario 1: Add Bank Account

**Source slice**: `docs/slices/05-add-bank-account.md`
**Business intent**: A user registers a bank account label so that transactions and statement uploads can be attributed to it.
**Domains involved**: accounts, notifications

#### Preconditions
- A valid authenticated user session exists (bearer token available).
- No pre-existing account with the same intent (nicknames are non-unique; this precondition is informational only).

#### Steps

1. `POST /api/v1/accounts/bank` with body `{"nickname": "HDFC Savings", "bank_name": "HDFC Bank", "account_type": "savings", "last4": "1234", "currency": "INR"}` → `201 Created` with `{"id": "<uuid>", "nickname": "HDFC Savings", "bank_name": "HDFC Bank", "account_type": "savings", "last4": "1234", "currency": "INR", "is_active": true}`
2. `GET /api/v1/accounts/` → `200 OK` with a list containing the newly created account entry.

#### Assertions
- **DB** (`bank_accounts`): Row exists with `nickname = 'HDFC Savings'`, `bank_name = 'HDFC Bank'`, `account_type = 'savings'`, `last4 = '1234'`, `currency = 'INR'`, `is_active = true`, `user_id = <authenticated user's id>`.
- **DB** (`credit_cards`): No row created.
- **DB** (`outbox`): Row exists with `event_type = 'accounts.AccountLinked'`, `payload.account_kind = 'bank'`, `payload.nickname = 'HDFC Savings'`.
- **API response**: `201` status, `id` is a valid UUID, `is_active = true`.
- **Events**: `accounts.AccountLinked` published to outbox in the same transaction as the `bank_accounts` insert.
- **Side effects**: After the outbox poller runs, the `notifications` domain creates an in-app notification with title "Account added" and body containing the account nickname and a deep-link to `/statements/upload?account_id=<id>`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `nickname` is empty or missing | `422 Unprocessable Entity` | [ ] |
| `bank_name` is empty or missing | `422 Unprocessable Entity` | [ ] |
| `account_type` is not one of `savings`, `current`, `salary`, `nre`, `nro` | `422 Unprocessable Entity` | [ ] |
| `last4` omitted | Account created without `last4`; no error | [ ] |
| `currency` omitted | Account created with `currency = 'INR'` (default) | [ ] |
| `currency` set to a non-INR value (e.g., `'USD'`) | Account created; `fx` domain includes the currency in its rate refresh | [ ] |
| `account_type = 'nre'` or `'nro'` | Stored as-is; no special business rules applied at this stage | [ ] |
| Duplicate nickname (same user, same label) | Second account created without error; both coexist with distinct `id` values | [ ] |
| Unauthenticated request | `401 Unauthorized` | [ ] |

---

### Scenario 2: Add Credit Card

**Source slice**: `docs/slices/06-add-credit-card.md`
**Business intent**: A user registers a credit card label so card transactions can be tracked separately and budgets can align with the card's billing cycle.
**Domains involved**: accounts, notifications, budgets (downstream, indirect)

#### Preconditions
- A valid authenticated user session exists.

#### Steps

1. `POST /api/v1/accounts/credit-cards` with body `{"nickname": "HDFC Millennia", "bank_name": "HDFC Bank", "card_network": "visa", "last4": "4521", "credit_limit": 150000.00, "billing_cycle_day": 15, "currency": "INR"}` → `201 Created` with `{"id": "<uuid>", "nickname": "HDFC Millennia", "bank_name": "HDFC Bank", "card_network": "visa", "last4": "4521", "credit_limit": 150000.00, "billing_cycle_day": 15, "currency": "INR", "is_active": true}`
2. `GET /api/v1/accounts/` → `200 OK` with the card appearing in the list.

#### Assertions
- **DB** (`credit_cards`): Row exists with `nickname = 'HDFC Millennia'`, `bank_name = 'HDFC Bank'`, `card_network = 'visa'`, `last4 = '4521'`, `credit_limit = 150000.00`, `billing_cycle_day = 15`, `currency = 'INR'`, `is_active = true`, `user_id = <authenticated user's id>`.
- **DB** (`bank_accounts`): No row created.
- **DB** (`outbox`): Row exists with `event_type = 'accounts.AccountLinked'`, `payload.account_kind = 'credit_card'`, `payload.nickname = 'HDFC Millennia'`.
- **API response**: `201` status, `id` is a valid UUID, `is_active = true`.
- **Events**: `accounts.AccountLinked` published to outbox in the same transaction as the `credit_cards` insert.
- **Side effects**: After the outbox poller runs, the `notifications` domain creates an in-app notification with title "Account added" and body containing the card nickname.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `nickname` is empty or missing | `422 Unprocessable Entity` | [ ] |
| `bank_name` is empty or missing | `422 Unprocessable Entity` | [ ] |
| `card_network` is not one of `visa`, `mastercard`, `amex`, `rupay` | `422 Unprocessable Entity` | [ ] |
| `billing_cycle_day = 0` | `422 Unprocessable Entity` (out of range 1–28) | [ ] |
| `billing_cycle_day = 29` | `422 Unprocessable Entity` (capped at 28) | [ ] |
| `billing_cycle_day = 30` | `422 Unprocessable Entity` (capped at 28) | [ ] |
| `billing_cycle_day = 31` | `422 Unprocessable Entity` (capped at 28) | [ ] |
| `billing_cycle_day` omitted | Card created; budgets for this card default to calendar months (1st–last day) | [ ] |
| `credit_limit` omitted | Card created; utilisation display is suppressed in UI | [ ] |
| `last4` omitted | Card created without `last4`; no error | [ ] |
| `card_network = 'amex'` | Stored normally; no special parser registered | [ ] |
| Unauthenticated request | `401 Unauthorized` | [ ] |

---

### Scenario 3: Edit Account Details

**Source slice**: `docs/slices/07-edit-account.md`
**Business intent**: A user updates the display name, billing cycle day, credit limit, or other metadata on an existing account.
**Domains involved**: accounts, budgets (indirect — future period anchors affected if `billing_cycle_day` changes)

#### Preconditions
- A valid authenticated user session exists.
- A `bank_accounts` or `credit_cards` row exists for the user with `is_active = true`.

#### Steps (Bank Account)

1. `GET /api/v1/accounts/` → `200 OK` with current account details listed (served via `user_accounts_summary` view).
2. `PATCH /api/v1/accounts/bank/<bank_account_id>` with body `{"nickname": "HDFC Joint"}` → `200 OK` with updated account details including `nickname = 'HDFC Joint'` and a refreshed `updated_at`.

#### Steps (Credit Card — billing_cycle_day change)

1. `GET /api/v1/accounts/` → `200 OK`.
2. `PATCH /api/v1/accounts/credit-cards/<credit_card_id>` with body `{"billing_cycle_day": 20}` → `200 OK` with updated `billing_cycle_day = 20` and refreshed `updated_at`.

#### Assertions
- **DB** (`bank_accounts`): `nickname = 'HDFC Joint'`, `updated_at` is more recent than `created_at`.
- **DB** (`credit_cards`): `billing_cycle_day = 20`, `updated_at` is more recent than `created_at`.
- **DB** (`outbox`): No new outbox row created (no event published for edits).
- **API response**: `200` status, updated fields reflected in response body.
- **Events**: None published.
- **Side effects**: `user_accounts_summary` view reflects the change immediately for all subsequent queries. Future budget periods using `period_anchor_day` derived from the credit card will use the new `billing_cycle_day`; existing `budget_progress` rows are not retroactively adjusted.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Rename to a nickname already used by another account | Allowed; nicknames are not unique | [ ] |
| `billing_cycle_day` changed to 29 on a credit card | `422 Unprocessable Entity` | [ ] |
| `billing_cycle_day` changed mid-active-budget-period | Change persisted; current `budget_progress` period is not recalculated; new anchor takes effect next period | [ ] |
| `currency` changed | Allowed; existing transactions retain their original currency; new transactions default to updated currency | [ ] |
| `bank_name` or `account_type` changed | Allowed; purely cosmetic, no downstream impact | [ ] |
| Account does not belong to the authenticated user | `403 Forbidden` or `404 Not Found` | [ ] |
| Account `is_active = false` | `404 Not Found` (inactive accounts are not surfaced in active queries) — TODO: confirm exact behaviour | [ ] |
| Unauthenticated request | `401 Unauthorized` | [ ] |

---

### Scenario 4: Deactivate Account (Soft Delete — has linked history)

**Source slice**: `docs/slices/08-deactivate-account.md`
**Business intent**: A user removes an account from active use while preserving all historical transactions and statements linked to it.
**Domains involved**: accounts, investments

#### Preconditions
- A valid authenticated user session exists.
- The account (`bank_accounts` or `credit_cards`) exists with `is_active = true`.
- At least one `transactions` row exists with `account_id = <this account>` (linked history path).

#### Steps

1. `DELETE /api/v1/accounts/bank/{account_id}` → `204 No Content` (account soft-deleted). Use `DELETE /api/v1/accounts/credit-cards/{card_id}` → `204 No Content` for credit card accounts.
2. `GET /api/v1/accounts/` → `200 OK` with the deactivated account absent from the active list (active accounts only — no `include_inactive` param confirmed).
3. After the outbox poller processes the `AccountRemoved` event (wait up to 5 s in integration tests), query `sip_registrations WHERE bank_account_id = :account_id` and assert `is_active = false` for any rows that matched.

#### Assertions
- **DB** (`bank_accounts` or `credit_cards`): `is_active = false`; all other columns including `id` and historical metadata unchanged; row still exists (not hard-deleted).
- **DB** (`transactions`): All rows where `account_id = <this account>` still exist and are unmodified; `account_id` references remain valid.
- **DB** (`statement_uploads`): All rows where `account_id = <this account>` still exist and are unmodified.
- **DB** (`outbox`): Row exists with `event_type = 'accounts.AccountRemoved'`, `payload.account_id = <this account>`, `payload.account_kind = 'bank'` or `'credit_card'`.
- **DB** (`sip_registrations`): `is_active = false` for all rows where `bank_account_id = <deactivated account>` after the `AccountRemoved` event is processed by the outbox poller.
- **API response**: Account is absent from the default `GET /api/v1/accounts/` list after deactivation.
- **Events**: `accounts.AccountRemoved` published to outbox.
- **Side effects**: After the outbox poller runs, the `investments` domain sets `is_active = false` on all `sip_registrations` where `bank_account_id = <this account> AND is_active = true`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Account has no linked transactions or statement uploads (hard-delete eligible) | Row is hard-deleted from `bank_accounts`/`credit_cards`; `AccountRemoved` published | [ ] |
| Attempt to hard-delete an account that actually has transactions | `409 Conflict` (or equivalent error) explaining that the account has transaction history and can only be soft-deactivated | [ ] |
| Account has open statement processing jobs (`extraction_jobs.status = 'classifying'`) | System warns the user; deactivation can proceed; in-progress workflows hold `account_id` in their state and complete regardless of `is_active` — TODO: confirm whether warning is advisory or blocking | [ ] |
| Account `is_active` is already `false` | `404 Not Found` or idempotent `200`/`204` — TODO: confirm exact behaviour | [ ] |
| Account does not belong to the authenticated user | `403 Forbidden` or `404 Not Found` | [ ] |
| Linked `sip_registrations` exist with `is_active = true` | All matching `sip_registrations` set to `is_active = false` after `AccountRemoved` is processed | [ ] |
| No linked `sip_registrations` exist | `AccountRemoved` processed without error; no `sip_registrations` rows affected | [ ] |
| Unauthenticated request | `401 Unauthorized` | [ ] |

---

### Scenario 5: Account Reactivation — NOT CURRENTLY SUPPORTED BY API

**Source slice**: `docs/slices/08-deactivate-account.md` (edge case — "Reactivating a soft-deleted account")
**Business intent**: When an account is reactivated, `is_active` would be set back to `true`. SIP registrations that were deactivated when the account was removed would NOT be automatically re-enabled — they would require manual re-enablement from the Investments screen.
**Domains involved**: accounts

#### Preconditions
- A valid authenticated user session exists.
- The account exists with `is_active = false` (previously soft-deleted).

#### Steps

No reactivation endpoint exists in the current API. The only way to reactivate at present is a direct DB update (admin operation only). This scenario is pending API implementation.

If a reactivation endpoint is added in the future, the expected flow would be:
1. User navigates to inactive accounts (display mechanism TBD — no `GET /api/v1/accounts/?include_inactive=true` param confirmed).
2. User triggers reactivation via the new endpoint → account row updated to `is_active = true`.
3. `GET /api/v1/accounts/` → `200 OK` with the account now appearing in the active list.

#### Assertions (expected once endpoint is implemented)
- **DB** (`bank_accounts` or `credit_cards`): `is_active = true`; `updated_at` refreshed.
- **DB** (`sip_registrations`): Rows that were deactivated when `AccountRemoved` was processed remain `is_active = false` — they are NOT automatically re-enabled.
- **DB** (`outbox`): No new outbox row (no event published for reactivation — per slice 08).
- **API response**: Account appears in active account list.
- **Events**: None published on reactivation.
- **Side effects**: Account would be immediately available again in transaction dropdowns, statement upload selectors, and all other active UI. SIP registrations require manual re-enablement from the Investments screen.

#### Edge Cases (pending implementation)

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User attempts to re-enable a deactivated SIP after reactivating the account | User must navigate to Investments screen and manually re-enable each SIP; system does not do this automatically | [ ] |
| Account already `is_active = true` (no-op reactivation) | `200` or `409` — TBD once endpoint is designed | [ ] |
| Account does not belong to the authenticated user | `403 Forbidden` or `404 Not Found` | [ ] |
| Unauthenticated request | `401 Unauthorized` | [ ] |

> TODO: `[ ]` Add `PATCH /api/v1/accounts/bank/{id}` with `is_active: true` to enable user-initiated reactivation — currently no endpoint exists

---

## Known Inconsistencies

The following entries from `docs/business-intent/INCONSISTENCIES.md` directly involve the accounts domain.

### [2.1] Statement date-range overlap detection attributed to `accounts`

- **Sources in conflict**: `business-intent/accounts.md` (lists "Statement date range tracking" as an accounts feature) vs. `domains/accounts.md` and `domains/statements.md` (overlap check runs inside `StatementProcessingWorkflow`, querying `statement_uploads` owned by the `statements` domain).
- **Impact for testing**: Do not write tests for overlap detection as an accounts API concern. Any test covering duplicate-import warnings belongs in the `statements` test guide, not here. The accounts domain provides the `account_id` grouping key only; the check itself is a `statements` domain responsibility.
- **Status**: Misattribution in documentation; no code change needed in the accounts domain, but `business-intent/accounts.md` should be corrected to read: "Enables overlap detection: accounts are the grouping key for which the `statements` domain checks for date-range overlaps."

### [3.5] Account reactivation / SIP registrations not auto-reactivated

- **Sources in conflict**: `business-intent/accounts.md` (original version describes deactivation but says nothing about reactivation) vs. `slices/08-deactivate-account.md` (edge case documents reactivation flow and the explicit constraint that SIP registrations are NOT automatically re-activated).
- **Impact for testing**: Scenario 5 is now marked "NOT CURRENTLY SUPPORTED BY API" — no reactivation endpoint exists in the current codebase. When a reactivation endpoint is eventually added, any test must assert that `sip_registrations.is_active` remains `false` after the account is restored, and that no `AccountLinked` or similar event is published. The "SIP re-enablement is manual" constraint must be verified as a deliberate outcome, not a bug.
- **Status**: No reactivation endpoint exists. Scenario 5 updated accordingly. `business-intent/accounts.md` should also be updated to reflect this gap.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| Reactivation endpoint path and method not documented in any slice or domain doc | `docs/slices/08-deactivate-account.md` (edge case only) | No endpoint exists — scenario updated. Add `PATCH /api/v1/accounts/bank/{id}` or equivalent to enable user-initiated reactivation; update slice 08 once implemented |
| Listing inactive accounts — endpoint variant unknown | `docs/slices/08-deactivate-account.md` | Confirmed: `GET /api/v1/accounts/` returns active accounts only; no `include_inactive` param exists. A separate endpoint or filter must be added if inactive account listing is needed |
| Hard-delete eligibility check — HTTP status code on rejection not specified | `docs/slices/08-deactivate-account.md` (Step 2B) | Confirm the exact error code and message returned when a hard-delete is attempted on an account with linked transactions |
| Behaviour when editing an inactive account | `docs/slices/07-edit-account.md` (precondition: `is_active = true`) | Document whether `PATCH` on an inactive account returns `404`, `403`, or `409` |
| Behaviour when deactivating an already-inactive account | `docs/slices/08-deactivate-account.md` | Document idempotency semantics for the deactivation endpoint |
| No event published on reactivation — intentional? | `docs/slices/08-deactivate-account.md` | If `investments` deactivates SIPs on `AccountRemoved`, should it receive any signal when the account is reactivated so users can be prompted? Confirm this is intentional and document in ADR if so |
| `user_accounts_summary` view — no dedicated test | `docs/domains/accounts.md` | Add a DB-level test verifying the view correctly unions `bank_accounts` and `credit_cards` with correct `account_kind` values |
| Notification content for credit card `AccountLinked` | `docs/slices/06-add-credit-card.md` (Step 4) | Slice 05 specifies a deep-link to `/statements/upload?account_id=<id>`; slice 06 does not confirm whether the same deep-link is included for credit cards |

---

## TODO

- ~~Confirm the reactivation endpoint path and method with the backend team before writing Scenario 5 step assertions~~ No endpoint exists — scenario updated. See Scenario 5.
- ~~Confirm the `GET /accounts?include_inactive=true` vs `GET /accounts/inactive` endpoint convention~~ No such param exists. `GET /api/v1/accounts/` returns active accounts only.
- [ ] Confirm the HTTP status code returned when a hard-delete is attempted on an account with linked transactions
- [ ] Confirm whether deactivating an already-inactive account is idempotent (`200`/`204`) or returns a `409`
- [ ] Confirm whether editing an inactive account returns `404` or another status
- [ ] Write DB-level tests for the `user_accounts_summary` view to ensure `account_kind` and `subtype` are correctly populated for both `bank_accounts` and `credit_cards`
- [ ] Add a test that verifies no PII (full account number, full card number) is ever stored or returned in API responses — only `last4`
- [ ] Verify the `fx` domain correctly picks up a non-INR currency after `AccountLinked` is consumed (Scenario 1 edge case for foreign-currency accounts)
- [ ] After Scenario 4, verify the `investments` domain's SIP deactivation via the outbox poller in an integration test (not just unit) — assert `sip_registrations.is_active = false WHERE bank_account_id = <deactivated account>`
- [ ] Add a test confirming no `outbox` row is written on account edit (Scenario 3)
- [ ] Add `PATCH /api/v1/accounts/bank/{id}` with `is_active: true` to enable user-initiated reactivation — currently no endpoint exists (Scenario 5)
- [ ] Cross-reference inconsistency [1.5] from INCONSISTENCIES.md: slice 29 promises a notification when a SIP is deactivated due to `AccountRemoved`, but `domains/notifications.md` has no handler for this — clarify whether this notification should be added before marking Scenario 4's SIP side effects complete
