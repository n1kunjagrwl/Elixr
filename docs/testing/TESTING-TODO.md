# E2E Testing — Master TODO List

> Generated: 2026-05-17
> Source: All domain test guides in docs/testing/

## Priority Key
- **High**: Gap would cause a silent regression in production (missing assertion on a core invariant)
- **Medium**: Gap reduces test coverage but failure would surface elsewhere
- **Low**: Nice-to-have or documentation improvement

---

## identity

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm identity API endpoint paths by reading `src/elixir/domains/identity/api.py` — all step assertions use placeholder paths (`/auth/register`, `/auth/login`, etc.) that may not match the implementation | identity-test-guide.md |
| High | Confirm HTTP status codes for OTP failure responses (`400` vs `422` vs `429`) — Scenarios 1 and 3 edge cases cite ambiguous status codes | identity-test-guide.md |
| High | Clarify what happens at the DB level when `POST /auth/login` is called for an unknown phone — does `OTPDeliveryWorkflow` create an `otp_requests` row before detecting no user? Scenario 5 DB assertion cannot be finalised without this | identity-test-guide.md |
| Medium | Determine whether `POST /auth/refresh` returns a new refresh token or only a new access token — Scenario 4 API response assertion is incomplete | identity-test-guide.md |
| Medium | Verify response time parity for anti-enumeration (Scenario 5 timing edge case) — requires a timing harness or `pytest` timing assertion | identity-test-guide.md |
| Low | Add a Playwright E2E test file at `client/tests/identity/` covering Scenarios 1–7 once endpoint contracts are confirmed | identity-test-guide.md |
| Low | Write slice `05-resend-otp.md` — no slice covers "resend OTP" as an explicit user-initiated action | identity-test-guide.md |

---

## accounts

| Priority | Item | Source |
|----------|------|--------|
| High | After Scenario 4, verify the `investments` domain's SIP deactivation via the outbox poller in an integration test — the assertion "sip_registrations are set to is_active = false" is currently a documentation claim only, not a verified step | accounts-test-guide.md |
| High | Add a test confirming no PII (full account number, full card number) is ever stored or returned in API responses — only `last4` | accounts-test-guide.md |
| Medium | Confirm the reactivation endpoint path and method with the backend team before writing Scenario 5 step assertions | accounts-test-guide.md |
| Medium | Confirm the `GET /accounts?include_inactive=true` vs `GET /accounts/inactive` endpoint convention | accounts-test-guide.md |
| Medium | Confirm the HTTP status code returned when a hard-delete is attempted on an account with linked transactions | accounts-test-guide.md |
| Medium | Confirm whether deactivating an already-inactive account is idempotent (`200`/`204`) or returns a `409` | accounts-test-guide.md |
| Medium | Confirm whether editing an inactive account returns `404` or another status | accounts-test-guide.md |
| Medium | Verify the `fx` domain correctly picks up a non-INR currency after `AccountLinked` is consumed — Scenario 1 edge case for foreign-currency accounts | accounts-test-guide.md |
| Medium | Cross-reference inconsistency [1.5]: slice 29 promises a notification when a SIP is deactivated due to `AccountRemoved`, but `domains/notifications.md` has no handler — clarify before marking Scenario 4's SIP side effects complete | accounts-test-guide.md |
| Low | Write DB-level tests for the `user_accounts_summary` view to ensure `account_kind` and `subtype` are correctly populated for both `bank_accounts` and `credit_cards` | accounts-test-guide.md |
| Low | Add a test confirming no `outbox` row is written on account edit (Scenario 3) | accounts-test-guide.md |
| Low | Add a test confirming no `outbox` row is written on account reactivation (Scenario 5) | accounts-test-guide.md |

---

## statements

| Priority | Item | Source |
|----------|------|--------|
| High | Decide whether ADK agent calls are mocked in E2E tests (via `page.route()`) or exercised against a real ADK sandbox — document the decision before writing tests | statements-test-guide.md |
| High | Resolve inconsistency [1.4] with the team: either define a `ClassificationAbandoned` event that triggers a "resume" push notification, or update `slices/11-resume-abandoned-statement.md` to remove the notification trigger | statements-test-guide.md |
| High | Add test confirming file is deleted from storage after parsing (`statement_uploads.file_path` no longer resolves to existing stored object) | statements-test-guide.md |
| Medium | Identify or provision a test statement PDF that reliably produces at least one low-confidence row to enable Scenario 2 without mocking the ADK agent | statements-test-guide.md |
| Medium | Implement a Temporal test harness for the 7-day timeout path (Scenario 5); consider using Temporal's `fast_forward_time` capability | statements-test-guide.md |
| Medium | Confirm whether the classify endpoint returns `404` or `409` when submitted against a completed or failed job — the slice does not specify the exact status code | statements-test-guide.md |
| Low | Add a Playwright test that verifies the SSE `overlap_warning` event is rendered visibly to the user in the UI | statements-test-guide.md |
| Low | Write tests for the `fx` domain interaction: verify non-INR transaction rows in a statement have their `currency` field correctly set in `ExtractionCompleted`'s payload | statements-test-guide.md |

---

## import_

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm whether the Splitwise CSV path bypasses or pre-fills the column mapping step — adjust Scenario 1 Splitwise edge case accordingly | import_-test-guide.md |
| High | Write a dedicated test for the `ImportCompleted` count discrepancy: import a file where some rows are also present in a prior statement upload; assert `import_jobs.imported_rows` differs from `SELECT COUNT(*) FROM transactions WHERE source = 'bulk_import'` and that the notification uses the import domain's count | import_-test-guide.md |
| Medium | Determine the exact HTTP status code returned when attempting to call a non-existent bulk-delete endpoint (`DELETE /import/{job_id}`) — update Scenario 4 assertion | import_-test-guide.md |
| Medium | Clarify parser behaviour when both `debit_amount` and `credit_amount` are non-zero in the same row — add as an edge case in Scenario 3 | import_-test-guide.md |
| Medium | Confirm `GET /import/{job_id}` response schema (field names, status enum values) against the API implementation before asserting API response shape | import_-test-guide.md |
| Medium | Add a test for the SSE stream: verify `status` transitions (`uploaded → awaiting_mapping → processing → completed`) are streamed in order | import_-test-guide.md |
| Low | Verify that `import_jobs.file_path` is deleted from storage on completion and also on failure (no orphaned files) | import_-test-guide.md |
| Low | Once (or if) a bulk-delete-import-batch feature is built, replace Scenario 4's workaround steps with the real feature flow | import_-test-guide.md |

---

## transactions

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm the HTTP contract for the duplicate fingerprint warning path (409 vs. warning flag + force parameter) — Scenario 3 assertions cannot be finalised | transactions-test-guide.md |
| High | Confirm whether `UNIQUE(user_id, fingerprint)` is a hard DB constraint or only a service-layer check; this determines whether a "force proceed" on a duplicate is even possible | transactions-test-guide.md |
| High | Add E2E auth isolation test: ensure user A cannot query user B's transactions by guessing IDs — assert 403/404 for cross-user transaction IDs | transactions-test-guide.md |
| High | Add dedicated test confirming `ExtractionPartiallyCompleted` handler never creates transactions for rows absent from the `classified_rows` payload | transactions-test-guide.md |
| High | Review slice 26 and update its edge case to remove the reference to transaction deletion (flagged in Known Inconsistencies) | transactions-test-guide.md |
| Medium | Confirm whether inactive accounts are blocked at the API level when creating a transaction (Scenario 1 edge case) | transactions-test-guide.md |
| Medium | Confirm whether the API enforces that exactly one item must have `is_primary = true` | transactions-test-guide.md |
| Medium | Confirm whether same-category multi-item splits (Scenario B from domain docs) are allowed via API | transactions-test-guide.md |
| Medium | Confirm whether the type-to-transfer edit also emits `changed_fields = ['items']` alongside `['type']` when category auto-changes to Self Transfer | transactions-test-guide.md |
| Medium | Confirm budget handler behaviour for credit-type transactions (whether credit categories can have budget goals) | transactions-test-guide.md |
| Medium | Confirm whether API enforces income-only categories for credit-type transactions at the server side | transactions-test-guide.md |
| Medium | Confirm page size: fixed at 50 or configurable via query param | transactions-test-guide.md |
| Medium | Confirm whether a result count cap applies to keyword search results | transactions-test-guide.md |
| Medium | Confirm exact cursor format and how invalid/stale cursors are handled | transactions-test-guide.md |
| Medium | Confirm `TransactionCategorized` vs `TransactionUpdated` — when items are replaced on an edit, is `TransactionCategorized` also re-published? | transactions-test-guide.md |
| Low | Write workflow integration test for `RecurringTransactionDetectionWorkflow` that seeds 90 days of debit transactions for the same merchant and asserts `source = 'recurring_detected'` | transactions-test-guide.md |
| Low | Extend Scenario 9 edge cases or add a separate scenario for transfer detection when the counterpart transaction comes from a prior import (not the same job) | transactions-test-guide.md |
| Low | Add E2E tests for `RecurringTransactionDetectionWorkflow` once the workflow is deployed | transactions-test-guide.md |

---

## categorization

| Priority | Item | Source |
|----------|------|--------|
| High | Resolve inconsistency 1.1 (default category deactivation) before writing the "hide a default category" test — the business intent and slice are contradictory | categorization-test-guide.md |
| High | Resolve inconsistency 1.3 ("Investment — SIP" category) before writing any SIP-related categorization tests | categorization-test-guide.md |
| High | Confirm whether `amount_gte`, `amount_lte`, and `source_account_id` are real columns in `categorization_rules` — they are referenced in tests but absent from `docs/domains/categorization.md`; do not write tests for columns that may not exist | categorization-test-guide.md |
| High | Define and document `suggest_category()` error behaviour when the ADK agent is unavailable or returns an empty result — Scenario 4 edge case "ADK unavailable" is currently TODO | categorization-test-guide.md |
| Medium | Confirm trim/normalisation behaviour for `match_type = 'exact'` rules | categorization-test-guide.md |
| Medium | Confirm whether the rule creation endpoint validates that `category_id` belongs to the requesting user | categorization-test-guide.md |
| Medium | Confirm the exact endpoint paths for category and rule CRUD from `src/elixir/domains/categorization/api.py` — current paths are placeholder | categorization-test-guide.md |
| Low | Add Playwright E2E tests for the frontend category picker and rule management screens once the API contract is stable | categorization-test-guide.md |
| Low | Link each scenario to its corresponding pytest test file path once tests are written (suggested: `tests/e2e/categorization/`) | categorization-test-guide.md |

---

## earnings

| Priority | Item | Source |
|----------|------|--------|
| High | Write a slice or API contract doc for the `POST /earnings/classify/{transaction_id}` endpoint before finalising Scenario 2 — the endpoint request shape and idempotency behaviour are undocumented | earnings-test-guide.md |
| High | Determine whether the outbox poller (2-second cycle) requires test helpers to advance time or flush the outbox synchronously — Scenarios 1 and 2 may need a `wait_for` step | earnings-test-guide.md |
| High | Verify that the `peer_contacts_public` SQL view is present and populated in the test database setup — missing this view will cause Scenario 1 and 2 handlers to error | earnings-test-guide.md |
| Medium | Read `docs/slices/21-classify-ambiguous-credit.md` and extend Scenario 2 with the full classification flow, including the peer-balance linking sub-path ([3.7]) | earnings-test-guide.md |
| Medium | Confirm the API endpoint paths and request/response schemas for `POST /earnings`, `GET /earnings`, `GET /earnings/dashboard`, etc. against `src/elixir/domains/earnings/api.py` | earnings-test-guide.md |
| Medium | Add a `docs/testing/earnings-heuristic-fixtures.md` with canonical test cases for score ≥ 0.85 (income), score ≥ 0.85 (peer), and ambiguous ranges — current heuristic scoring is described in prose only | earnings-test-guide.md |
| Low | Clarify whether `earning_sources` hard-delete is supported in addition to soft-deactivation | earnings-test-guide.md |
| Low | Add Playwright E2E counterparts for Scenarios 3, 4, 5, and 7 once the frontend screens exist | earnings-test-guide.md |

---

## budgets

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm the exact endpoint shape for deactivation (Scenario 9) — `PATCH`, `DELETE`, or dedicated action URL | budgets-test-guide.md |
| High | Add integration tests for `fx.convert()` path in Scenarios 3 and 7 once the fx domain test guide defines mock FX rate setup | budgets-test-guide.md |
| Medium | Confirm deduplication key for `budget_alerts`: is the unique constraint on `(goal_id, period_start, threshold_percent)` exactly? Needed for Scenario 10 edge case when limit changes between alert firings | budgets-test-guide.md |
| Medium | Clarify dashboard response when an active goal has no `budget_progress` row for the current period — omitted from results, or returned with `current_spend = 0`? | budgets-test-guide.md |
| Medium | Add test for salary-aligned period resolution (`period_anchor_day`) mid-month creation — assert correct `period_start` and `period_end` in `budget_progress` | budgets-test-guide.md |
| Medium | Add test for weekly period boundary (Monday–Sunday rollover) — assert two separate `budget_progress` rows for week N and week N+1 | budgets-test-guide.md |
| Medium | Add test for custom period goal (`period_type = "custom"`) end-to-end — creation, spend tracking, alert | budgets-test-guide.md |
| Low | Verify whether `budget_progress` rows for prior periods are accessible through the API (needed for Scenario 6 previous-period navigation test) | budgets-test-guide.md |
| Low | Once `rollover` is implemented, add scenarios for effective limit calculation and threshold checks against the effective limit | budgets-test-guide.md |

---

## investments

| Priority | Item | Source |
|----------|------|--------|
| High | Resolve category name inconsistency [1.3]: confirm whether `"Investment — SIP"` or `"Investments (outflow)"` should be assigned on SIP confirmation (Scenario 4) | investments-test-guide.md |
| High | Resolve SIP deactivation notification gap [1.5]: decide and document whether a `SIPRegistrationDeactivated` event and notification are in scope | investments-test-guide.md |
| High | Write a slice for holding deletion and add a corresponding test scenario to this guide — currently no slice exists | investments-test-guide.md |
| Medium | Add unique-constraint documentation to `business-intent/investments.md` for the one-holding-per-instrument rule [3.12] | investments-test-guide.md |
| Medium | Write per-data-source contract tests for `MarketPriceFetchWorkflow` (AMFI, Eodhd, CoinGecko, Twelve Data, metals-api) | investments-test-guide.md |
| Medium | Write formula coverage tests for `CalculatedValuationWorkflow` (PPF, RD, bond, NPS types beyond FD) | investments-test-guide.md |
| Medium | Add FD maturity notification test scenario once the notification event is confirmed to be published | investments-test-guide.md |
| Medium | Add instrument search endpoint test scenario | investments-test-guide.md |
| Low | Determine and document the SIP re-activation policy after account restore; add corresponding assertion in SIP edge case tests | investments-test-guide.md |

---

## peers

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm the exact API route shape for settlements: `POST /peers/balances/{id}/settlements` or a top-level `POST /peers/settlements`? Update route references in all scenarios once confirmed | peers-test-guide.md |
| High | Confirm whether negative settlement amounts (used for corrections in Scenario 8) are accepted by the schema validation layer or require a separate endpoint | peers-test-guide.md |
| Medium | Clarify whether `linked_transaction_id` on a balance creation is validated for user ownership of the referenced transaction (currently marked TODO in Scenario 5 edge cases) | peers-test-guide.md |
| Medium | Add a scenario asserting `peer_contacts_public` view is filtered correctly per `user_id` (no cross-user data leakage) | peers-test-guide.md |
| Medium | Add read-path scenarios (list contacts, list balances per peer, view settlement history for a balance) once API contracts are finalised | peers-test-guide.md |
| Low | Confirm the HTTP status code returned when deletion is blocked by open balances — `409 Conflict` is assumed; verify against implementation | peers-test-guide.md |
| Low | Determine whether `GET /peers/balances?peer_id=<id>` or `GET /peers/contacts/<id>/balances` is the correct route | peers-test-guide.md |

---

## notifications

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm idempotency behaviour for `PATCH /notifications/{id}/read` when called on an already-read notification: does `read_at` stay unchanged (first-write-wins) or update to now (last-write-wins)? | notifications-test-guide.md |
| High | Define `ClassificationAbandoned` event (for workflow paused mid-classification), add handler in notifications domain, then add a Scenario for the resume notification | notifications-test-guide.md |
| High | Define `SIPRegistrationDeactivated` event (for silent SIP deactivation when account removed), add handler, then add a Scenario here | notifications-test-guide.md |
| Medium | Confirm the 90-day archival cutoff: is it enforced at the query level (API excludes old rows) or at a scheduled cleanup job? Add a DB-level assertion | notifications-test-guide.md |
| Medium | Confirm whether `GET /notifications` (no filter) also applies the 90-day cutoff or returns the full history | notifications-test-guide.md |
| Low | Add Playwright E2E tests for the frontend notification bell badge: verify badge count decrements on read and drops to zero after read-all | notifications-test-guide.md |
| Low | Verify that `user_id` isolation is enforced at both the application layer and PostgreSQL RLS for all notification endpoints | notifications-test-guide.md |

---

## fx

| Priority | Item | Source |
|----------|------|--------|
| High | Confirm that `FXRateRefreshWorkflow` actually queries `bank_accounts`, `credit_cards`, and `instruments` inside a Temporal **activity** (not the workflow itself) to preserve determinism — if the DB query runs in workflow code, it violates the Temporal determinism constraint | fx-test-guide.md |
| High | Clarify DB retention policy for `fx_rates` — the unique constraint means only one row per pair is kept (upserted); the `as_of_date` parameter in `convert()` implies historical rows, but the upsert pattern overwrites history — Scenario for historical rate lookup cannot be written until retention is resolved | fx-test-guide.md |
| High | Determine the exact error contract for `FXRateUnavailableError` — which HTTP status code does each calling domain surface to the client? (Scenarios 5, 6, 7 edge cases) | fx-test-guide.md |
| Medium | Verify that inverse rate rows (INR→USD, INR→EUR, etc.) are stored correctly and that `convert()` uses them for the `from_currency == 'INR'` branch | fx-test-guide.md |
| Medium | Document the cold-start handling: does the app block requests or return errors until the first successful `FXRateRefreshWorkflow` run? | fx-test-guide.md |
| Low | Add Playwright E2E tests for multi-currency display in the portfolio screen and transaction list | fx-test-guide.md |
| Low | Confirm free-tier rate limit sufficiency: 4 runs/day × 1 API call per run = ~120 calls/month against a 1,500/month free limit | fx-test-guide.md |

---

## Cross-Domain TODOs

Items that span multiple domains or require coordination between domain owners.

| Priority | Item | Domains |
|----------|------|---------|
| High | Write a full chain E2E test: upload statement → `ExtractionCompleted` → transactions created → `TransactionCategorized` → `budget_progress` updated → `BudgetLimitWarning` fired → notification created. Currently these three hops are tested independently with injected events only. | statements, transactions, budgets, notifications |
| High | Write a full chain E2E test: manual credit transaction → `TransactionCreated` → earnings handler → `EarningClassificationNeeded` → notification created → user classifies → `EarningRecorded` | transactions, earnings, notifications |
| High | Write an E2E test verifying `AccountRemoved` → investments SIP deactivation → assert `sip_registrations.is_active = false` as a live cross-domain assertion (not just documentation). | accounts, investments |
| High | Write an E2E test for `SIPDetected` → notification → user confirmation → `SIPLinked` as a single end-to-end scenario (not individual injected events). | investments, notifications |
| High | Verify `peer_contacts_public` view is correctly filtered by `user_id` and that the earnings heuristic correctly skips `EarningRecorded` when a credit description matches a peer name. | peers, earnings |
| Medium | Create a shared test fixture library that seeds: identity user, accounts (bank + credit card), system category defaults, and a baseline `fx_rates` row — required by almost all domain test suites as a precondition. | all |
| Medium | Document and enforce test execution order (see REVIEW.md §5) — fx → identity → categorization → accounts → peers → notifications → statements → import_ → transactions → earnings → budgets → investments. | all |
| Medium | Confirm that `StatementUploaded` event has no current consumer — either remove the event if unused, or document the intended consumer. | statements |
| Medium | Confirm that `CategoryCreated` event has no current consumer — either remove the event if unused, or document the intended consumer. | categorization |
| Medium | Confirm that `EarningRecorded` event has no current consumer — either remove the event if unused, or document the intended consumer. | earnings |
| Medium | Confirm that `SIPLinked` event has no current consumer — either add a notifications handler or document as intentionally unconsumed. | investments, notifications |
| Medium | Confirm that `ValuationUpdated` event has no current consumer — explicitly document the decision not to notify users on portfolio revaluation. | investments, notifications |
| Low | Write a shared `conftest.py` (or Playwright setup fixture) that provisions test data in the correct domain order and tears it down after each test suite. | all |

---

## Missing Slices (from INCONSISTENCIES.md §4)

These user flows have no complete slice and limited or no test coverage.

| Priority | Missing slice | Status | Implied by |
|----------|--------------|--------|------------|
| High | **Browse / search transaction list** | Slice 44 now exists; transactions-test-guide.md Scenarios 11–17 cover it; endpoint contract and Playwright tests still TODO | `business-intent/transactions.md`; `docs/slices/44-browse-search-transactions.md` |
| High | **Delete or roll back an import batch** | Slice 43 exists; import_-test-guide.md Scenario 4 documents the workaround path only — no bulk delete endpoint exists; if feature is built, a real Scenario 4 needs to be written | `business-intent/import_.md`; `docs/slices/43-delete-import-batch.md` |
| Medium | **View all earning sources and their totals** | No test scenario written; earnings-test-guide.md Coverage Gaps explicitly flags this; no slice for the "source totals summary view" exists | `business-intent/earnings.md` — "see how much I earned from freelancing this year" |
| Medium | **Delete an investment holding** | No slice exists; investments-test-guide.md Coverage Gaps flags this; currently no API endpoint documented | `slices/27-add-investment-holding.md` — "edit the existing holding" implies deletion, but no delete flow is documented |
| Medium | **View earnings dashboard / income summary** | Slice 38 now exists; earnings-test-guide.md Scenario 5 covers it; endpoint path and response schema not yet confirmed against implementation | `business-intent/earnings.md`; `docs/slices/38-view-earnings-dashboard.md` |
| Low | **Edit an existing earning record** | Slice 39 now exists; earnings-test-guide.md Scenario 6 covers it; endpoint path not confirmed | `business-intent/earnings.md`; `docs/slices/39-edit-earning.md` |
| Low | **Edit / delete a peer contact** | Slice 40 now exists; peers-test-guide.md Scenarios 10–13 cover it; API route shapes not fully confirmed | `slices/33-add-peer-contact.md`; `docs/slices/40-edit-delete-peer-contact.md` |
| Low | **Edit an investment holding** | Slice 41 now exists; investments-test-guide.md Scenario 8 covers it; Playwright test not written | `slices/27-add-investment-holding.md`; `docs/slices/41-edit-investment-holding.md` |
| Low | **Edit / deactivate a budget goal** | Slice 42 now exists; budgets-test-guide.md Scenarios 8 and 9 cover it; deactivation endpoint shape not confirmed | `slices/26-budget-alert-response.md`; `docs/slices/42-edit-deactivate-budget.md` |
