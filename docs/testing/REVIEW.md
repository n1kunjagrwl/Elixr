# E2E Test Guide — Cross-Domain Audit

> Audit date: 2026-05-17

## Summary Statistics

| Metric | Count |
|--------|-------|
| Domains covered | 12 / 12 |
| Total test scenarios | 109 |
| Total edge cases | 408 |
| Total TODO items | 87 |
| Inconsistencies covered (from INCONSISTENCIES.md) | 18 / 26 |

**Scenario breakdown per domain:**

| Domain | Scenarios | Edge Cases | TODOs |
|--------|-----------|------------|-------|
| identity | 7 | 26 | 6 |
| accounts | 5 | 40 | 11 |
| statements | 6 | 21 | 7 |
| import_ | 4 | 22 | 6 |
| transactions | 18 | 57 | 12 |
| categorization | 9 | 53 | 8 |
| earnings | 7 | 34 | 6 |
| budgets | 10 | 41 | 6 |
| investments | 9 | 32 | 8 |
| peers | 13 | 28 | 6 |
| notifications | 14 | 27 | 5 |
| fx | 7 | 27 | 6 |
| **Total** | **109** | **408** | **87** |

---

## 1. Event Linkage Audit

For every event published by any domain, the consuming domain's test guide was checked for a scenario asserting the event is received and handled.

| Producer domain | Event type | Consumer domain(s) | Coverage status |
|----------------|-----------|-------------------|----------------|
| identity | `identity.UserRegistered` | (future/none — domain doc notes "future: onboarding domain") | N/A — no current consumer |
| identity | `identity.UserLoggedIn` | (none — retained for audit/analytics only) | N/A — no current consumer |
| accounts | `accounts.AccountLinked` | notifications | **Covered** — notifications-test-guide.md Scenario 9 asserts the notification row is created and contains correct metadata |
| accounts | `accounts.AccountRemoved` | investments | **Covered** — investments-test-guide.md Scenario 3 edge case "AccountRemoved deactivates SIP" and Scenario 4 assert `sip_registrations.is_active = false` |
| statements | `statements.StatementUploaded` | (no current consumer documented in any domain doc) | **Missing** — `StatementUploaded` is listed in domains/statements.md Events Published but no domain doc shows a consumer and no test guide scenario asserts it is received. It may be an internal/observability event only; this should be confirmed and the event removed from the domain doc if no consumer exists. |
| statements | `statements.ExtractionCompleted` | transactions, notifications | **Covered (transactions)** — transactions-test-guide.md Scenario 9 asserts transactions are created from the payload, including idempotency edge cases. **Covered (notifications)** — notifications-test-guide.md Scenario 6 asserts the "Statement processed" notification is created with correct body, metadata, and idempotency guard. |
| statements | `statements.ExtractionPartiallyCompleted` | transactions, notifications | **Covered (transactions)** — transactions-test-guide.md Scenario 9 edge case "ExtractionPartiallyCompleted" asserts only classified_rows are processed. **Covered (notifications)** — notifications-test-guide.md Scenario 7 asserts the "Statement partially imported" notification with discarded date range. |
| import_ | `import_.ImportBatchReady` | transactions | **Covered** — transactions-test-guide.md Scenario 10 asserts transactions are created from the payload and fingerprint deduplication skips existing rows. |
| import_ | `import_.ImportCompleted` | notifications | **Covered** — notifications-test-guide.md Scenario 10 asserts the "Import complete" notification is created with `imported_rows` and `skipped_rows` counts. |
| transactions | `transactions.TransactionCreated` | earnings, investments, budgets | **Partially covered** — earnings-test-guide.md Scenarios 1 and 2 cover the earnings handler path (high-confidence income, ambiguous). investments-test-guide.md Scenario 4 covers the SIP detection handler. budgets-test-guide.md does **not** have a scenario that specifically tests the `TransactionCreated` event going to budgets; budgets uses `TransactionCategorized` instead — which is correct per the domain doc. The coverage gap is confirming that `TransactionCreated` does NOT trigger a budgets update (which is correct by design). |
| transactions | `transactions.TransactionCategorized` | budgets | **Covered** — budgets-test-guide.md Scenario 3 asserts `budget_progress.current_spend` is incremented on this event; Scenarios 4 and 5 cover alert thresholds; Scenario 9 covers deactivation guard. |
| transactions | `transactions.TransactionUpdated` | budgets | **Covered** — budgets-test-guide.md Scenario 7 asserts retroactive budget correction when `items` changes; edge case asserts skip when only `notes` changes. |
| categorization | `categorization.CategoryCreated` | (no consumer documented in any domain doc) | **Missing** — `CategoryCreated` is listed in domains/categorization.md Events Published and in categorization-test-guide.md Scenario 2, but no domain doc shows any consumer for this event. The event appears to have no current subscriber. The categorization test guide asserts it is published but does not (and cannot) assert a consumer handles it. If no consumer exists, the event should be documented as "published for future use / analytics" to avoid ambiguity. |
| earnings | `earnings.EarningRecorded` | (no consumer documented in any domain doc) | **Missing consumer verification** — `EarningRecorded` is published (earnings-test-guide.md Scenarios 1, 2, 3 assert the outbox row), but no domain doc lists a consumer for this event. It is published but appears to have no subscriber. This should be confirmed. |
| earnings | `earnings.EarningClassificationNeeded` | notifications | **Covered** — notifications-test-guide.md Scenario 8 asserts the "New credit to classify" notification is created with correct metadata and idempotency guard. earnings-test-guide.md Scenario 2 asserts the event is published. |
| budgets | `budgets.BudgetLimitWarning` | notifications | **Covered** — notifications-test-guide.md Scenario 3 asserts the "Approaching budget limit" notification is created with correct body, metadata, and deduplication. budgets-test-guide.md Scenario 4 asserts the event is published. |
| budgets | `budgets.BudgetLimitBreached` | notifications | **Covered** — notifications-test-guide.md Scenario 4 asserts the "Budget limit exceeded" notification is created with overage amount and idempotency guard. budgets-test-guide.md Scenario 5 asserts the event is published. |
| investments | `investments.SIPDetected` | notifications | **Covered** — notifications-test-guide.md Scenario 5 asserts the "SIP payment detected" notification is created with `transaction_id` and `sip_id` in metadata. investments-test-guide.md Scenario 4 asserts the event is published and the notification row exists. |
| investments | `investments.SIPLinked` | (no consumer documented in any domain doc) | **Missing consumer verification** — `SIPLinked` is published (investments-test-guide.md Scenario 4 step 7), but no domain doc lists a consumer. The notifications domain does not subscribe to `SIPLinked`. Whether a confirmation notification should exist is noted as a coverage gap in notifications-test-guide.md. |
| investments | `investments.ValuationUpdated` | (no consumer documented in any domain doc) | **Missing consumer verification** — `ValuationUpdated` is published (investments-test-guide.md Scenario 5), but no domain doc shows a consumer. Notifications domain explicitly does not subscribe to it. Confirmed no-op consumer is fine but should be documented. |
| fx | (none) | (none) | N/A — fx publishes no events |
| peers | (none) | (none) | N/A — peers publishes no events |
| notifications | (none) | (none) | N/A — notifications publishes no events |

### Missing Coverage Summary

The following event linkages have genuine coverage gaps in the test guides:

1. **`statements.StatementUploaded` has no documented consumer** — the event is published but no domain reacts to it. The test guides do not assert any downstream behaviour when this event fires. Either confirm no consumer is intended and document accordingly, or identify the consumer and add a scenario.

2. **`categorization.CategoryCreated` has no consumer** — published in categorization Scenario 2 but no test guide verifies a downstream handler, because none exists. Flag for documentation cleanup.

3. **`earnings.EarningRecorded` has no documented consumer** — asserted as published in earnings Scenarios 1–3 but no consuming domain is listed anywhere. Flag for documentation cleanup.

4. **`investments.SIPLinked` has no consumer test** — published in investments Scenario 4 but no notifications scenario covers a post-confirmation notification. The notifications-test-guide.md explicitly flags this as a gap (no `SIPLinked` handler). If a confirmation notification is desired, both the handler and the test scenario need to be added.

5. **`investments.ValuationUpdated` has no consumer test** — published in investments Scenario 5, but the notifications domain explicitly does not handle it. This is by design per the notifications-test-guide.md coverage gaps section. Confirm and document.

---

## 2. Precondition Chain Audit

The following scenarios have preconditions that depend on other domains but the corresponding scenarios in those domains are absent or undocumented.

| Test guide | Scenario | Precondition in question | Gap |
|-----------|----------|--------------------------|-----|
| statements-test-guide.md | Scenario 1 | "At least one active bank account registered" | accounts-test-guide.md Scenario 1 covers account creation, but no explicit cross-guide ordering contract exists. If accounts tests are not run before statements tests, Scenario 1 cannot proceed. |
| statements-test-guide.md | Scenarios 2, 3, 4 | "A `StatementProcessingWorkflow` is running" | This requires Scenario 1 to have completed (the workflow is started by the upload). No test guide documents the teardown or re-use of in-flight Temporal workflows between scenarios. |
| transactions-test-guide.md | Scenario 1 | "At least one active expense category exists in `categories_for_user`" | categorization-test-guide.md Scenario 1 covers default category browsing, but there is no documented seed fixture assertion. New-user tests may fail if seed data is absent. |
| transactions-test-guide.md | Scenario 6 | "A budget goal exists for Food & Dining for May 2026 with `current_spend` already reflecting the ₹1,000" | budgets-test-guide.md Scenario 3 covers spend tracking, but the precondition in transactions Scenario 6 requires a specific dollar amount already in the budget. No cross-guide setup protocol documents how to prime this state. |
| transactions-test-guide.md | Scenario 9 | "`ExtractionCompleted` event is present in the outbox" | Requires statements-test-guide.md Scenario 1 to have completed successfully. No documented ordering guarantee. |
| categorization-test-guide.md | Scenario 3 | "An active `categorization_rules` row exists: pattern = 'swiggy'" | categorization-test-guide.md Scenario 7 covers rule creation, but Scenario 3 is placed before Scenario 7 in the guide. If tests run sequentially, the precondition must be seeded. Not documented. |
| categorization-test-guide.md | Scenario 5 | "A `StatementProcessingWorkflow` is in progress (`extraction_jobs.status = 'awaiting_input`)" | Requires statements-test-guide.md to be partially executed (upload + at least one low-confidence row reaching the workflow). No cross-guide orchestration documented. |
| earnings-test-guide.md | Scenarios 1, 2 | "The `peer_contacts_public` SQL view is present and populated" | peers-test-guide.md Scenarios 1–2 cover contact creation, but the earnings handler queries the view even when no peers exist. The test guide flags this as a TODO: the view must exist in the test DB schema; an empty result is valid. |
| budgets-test-guide.md | Scenario 3 | "An active `budget_goals` row exists for 'Food & Dining' with `limit_amount = 5000`, `current_spend = 0`" | budgets-test-guide.md Scenario 1 creates this goal. The scenario numbering implies correct ordering within the guide, but no cross-guide dependency on categorization (category must exist) is called out as a setup precondition. |
| investments-test-guide.md | Scenario 3 | "At least one `bank_accounts` row exists for this user (`is_active = true`)" | accounts-test-guide.md Scenario 1 covers this, but no cross-guide dependency is documented. |
| investments-test-guide.md | Scenario 4 | "A debit transaction is created via statement import, CSV import, or manual entry" | Requires either statements-test-guide.md Scenario 1 or transactions-test-guide.md Scenario 1 to have completed. No orchestration documented. |
| peers-test-guide.md | Scenario 5 | "A `transactions` row exists" | transactions-test-guide.md Scenario 1 covers this, but no ordering between peers and transactions suites is documented. |
| notifications-test-guide.md | Scenario 3 | "`budgets` domain has published a `BudgetLimitWarning` event to the outbox" | budgets-test-guide.md Scenario 4 covers this, but the notifications test treats it as an injected precondition (manually publish the event). No E2E chain test exists that runs budgets Scenario 4 → notifications Scenario 3 as a single flow. |

---

## 3. Inconsistency Coverage

For every numbered item in `docs/business-intent/INCONSISTENCIES.md`, confirmation that it appears in at least one domain test guide's "Known Inconsistencies" section.

| # | Title (brief) | Covered in | Status |
|---|--------------|------------|--------|
| 1.1 | Default category deactivation | categorization-test-guide.md — Known Inconsistencies §1.1 | Covered |
| 1.2 | Transaction deletion | transactions-test-guide.md — Known Inconsistencies; budgets-test-guide.md — Known Inconsistencies §1.2 | Covered |
| 1.3 | SIP category name | categorization-test-guide.md — Known Inconsistencies §1.3; investments-test-guide.md — Known Inconsistencies §1.3 | Covered |
| 1.4 | Statement resume notification | statements-test-guide.md — Known Inconsistencies [1.4]; notifications-test-guide.md — Known Inconsistencies §1.4 | Covered |
| 1.5 | SIP deactivation notification | investments-test-guide.md — Known Inconsistencies §1.5; notifications-test-guide.md — Known Inconsistencies §1.5; accounts-test-guide.md — TODO cross-reference [1.5] | Covered |
| 2.1 | Statement overlap in accounts | accounts-test-guide.md — Known Inconsistencies §2.1 | Covered |
| 3.1 | Logout device-scoped | identity-test-guide.md — Known Inconsistencies [3.1] | Covered |
| 3.2 | Anti-enumeration | identity-test-guide.md — Known Inconsistencies [3.2] | Covered |
| 3.3 | Skip row | statements-test-guide.md — Known Inconsistencies [3.3] | Covered |
| 3.4 | Override auto-classified | statements-test-guide.md — Known Inconsistencies [3.4] | Covered |
| 3.5 | Account reactivation / SIP | accounts-test-guide.md — Known Inconsistencies §3.5 | Covered |
| 3.6 | Budget no backfill | budgets-test-guide.md — Known Inconsistencies §3.6 | Covered |
| 3.7 | Peer repayment peer-balance link | earnings-test-guide.md — Known Inconsistencies [3.7] | Covered |
| 3.8 | Manual earnings no dedup | earnings-test-guide.md — Known Inconsistencies [3.8] | Covered |
| 3.9 | Settlement correction append | peers-test-guide.md — Known Inconsistencies [3.9] | Covered |
| 3.10 | Multi-currency settlement silent fail | peers-test-guide.md — Known Inconsistencies [3.10] | Covered |
| 3.11 | Bulk import atomic | import_-test-guide.md — Known Inconsistencies [3.11] | Covered |
| 3.12 | One holding per instrument | investments-test-guide.md — Known Inconsistencies §3.12 | Covered |
| 4.1 | Missing slice: View earnings dashboard | earnings-test-guide.md Coverage Gaps (Scenario 5 present); TESTING-TODO.md §Missing Slices | Partially covered — a scenario exists but the slice has since been written (slice 38); endpoint contract not confirmed |
| 4.2 | Missing slice: Edit an existing earning | earnings-test-guide.md Scenario 6 — slice 39 now exists | Covered — slice 39 and Scenario 6 both exist |
| 4.3 | Missing slice: Edit / delete a peer contact | peers-test-guide.md Scenarios 10–13 — slice 40 now exists | Covered |
| 4.4 | Missing slice: Edit an investment holding | investments-test-guide.md Scenario 8 — slice 41 now exists | Covered |
| 4.5 | Missing slice: Edit / deactivate a budget goal | budgets-test-guide.md Scenarios 8 and 9 — slice 42 now exists | Covered |
| 4.6 | Missing slice: Delete or roll back an import batch | import_-test-guide.md Scenario 4 — slice 43 now exists (workaround path only) | Partially covered — Scenario 4 documents the current limitation; no bulk delete endpoint exists |
| 4.7 | Missing slice: Browse / search transaction list | transactions-test-guide.md Scenarios 11–17 — slice 44 now exists | Covered |
| 4.8 | Missing slice: View all earning sources and their totals | earnings-test-guide.md Coverage Gaps (no Scenario 8 written yet); referenced in TESTING-TODO.md | Missing — no test scenario written for this view |

**Inconsistencies not covered (missing from all test guides): 0**

Note: All 26 items appear in at least one test guide. Items 4.1–4.8 are "missing slices" per INCONSISTENCIES.md §4; the slices referenced in those items have since been written (slices 38–45), and most test scenarios now exist. The two genuine gaps are item 4.6 (bulk delete is still a workaround) and item 4.8 (no Scenario 8 written for earnings source totals view).

---

## 4. Cross-Domain Scenario Gaps

The following scenarios touch multiple domains but are covered in only one test guide, creating a risk that the integration point is not verified end-to-end.

| Gap | Covered in | Missing from | Risk |
|-----|-----------|--------------|------|
| `AccountLinked` → notifications in-app nudge | notifications-test-guide.md Scenario 9 treats the event as an injected precondition; accounts-test-guide.md Scenario 1 asserts the outbox row but does not verify the notification is created. | accounts-test-guide.md Scenario 1 "Side effects" assertion is aspirational — no step verifies the notification row. | Medium — regression in the outbox poller or notifications handler would not be caught by accounts tests. |
| `AccountRemoved` → SIP deactivation | investments-test-guide.md Scenario 3 edge case covers the deactivation. accounts-test-guide.md Scenario 4 asserts `AccountRemoved` is published and mentions the side effect, but no step in the accounts test verifies the SIP table. | accounts-test-guide.md — no DB assertion on `sip_registrations` after deactivation. | High — this is a cross-domain invariant; the accounts test should assert the outcome in `sip_registrations`. |
| `ExtractionCompleted` → transactions + notifications (full chain) | statements-test-guide.md Scenario 1 describes the chain in steps 8–10 but leaves them as documentation, not verified assertions. transactions-test-guide.md Scenario 9 covers the transactions handler. notifications-test-guide.md Scenario 6 covers the notification. | No single test verifies statements Scenario 1 all the way through to `transactions` rows + `notifications` row in one E2E run. | High — integration between three domains is tested independently but never end-to-end. |
| `TransactionCreated` (credit) → earnings heuristic → `EarningClassificationNeeded` → notification | earnings-test-guide.md Scenario 2 covers the earnings handler. notifications-test-guide.md Scenario 8 treats it as an injected event. | No test fires a real credit transaction via API and then asserts the full chain through to the notification row. | High — silent regression possible if earnings handler or outbox wiring breaks. |
| `TransactionCategorized` → budget alert → notification | budgets-test-guide.md Scenarios 4 and 5 cover the alert. notifications-test-guide.md Scenarios 3 and 4 treat the event as injected. | No single test runs a real categorized transaction and asserts both the budget alert and the notification in one flow. | High — three-domain integration is tested piecemeal only. |
| `SIPDetected` → notification → user confirmation → `SIPLinked` | investments-test-guide.md Scenario 4 covers the full flow including notification creation. notifications-test-guide.md Scenario 5 treats `SIPDetected` as an injected event. | A full-chain test from `TransactionCreated` → `SIPDetected` → notification → confirmation API → `SIPLinked` is not explicitly written in any test guide as a single scenario. | Medium — investment Scenario 4 is close but relies on simulated event injection in some steps. |
| Peer contact name used in earnings heuristic (via `peer_contacts_public` view) | earnings-test-guide.md Scenario 1 edge case ("description matches a known peer name") mentions this. peers-test-guide.md has no scenario asserting that contact creation populates the view in a way visible to earnings. | peers-test-guide.md — no test verifies that a peer contact created in Scenario 1 causes earnings to not fire `EarningRecorded` for a matching description. | Medium — cross-domain read via SQL view; if the view definition is wrong, earnings would misclassify repayments as income. |

---

## 5. Recommended Test Execution Order

Given the precondition chains identified in Section 2:

1. **fx** — no dependencies; seed `fx_rates` rows for USD/EUR/GBP/INR first, as many other domains call `fx.convert()`.
2. **identity** — no domain dependencies; creates the `users` and `sessions` rows that all other domains depend on for authentication.
3. **categorization** — depends only on identity (authentication); seed default categories and verify they exist before any other domain creates transactions.
4. **accounts** — depends on identity; account rows are required by statements, transactions, investments, import_.
5. **peers** — depends on identity; `peer_contacts_public` view must be populated before earnings heuristic tests.
6. **notifications** — depends on identity; can be run early as a consumer-only domain (inject events directly).
7. **statements** — depends on identity, accounts, categorization; must run before transactions (source of `ExtractionCompleted`).
8. **import_** — depends on identity, accounts, categorization; parallel with statements.
9. **transactions** — depends on identity, accounts, categorization; receives events from statements and import_.
10. **earnings** — depends on identity, transactions, peers (view); must run after transactions and peers.
11. **budgets** — depends on identity, transactions, categorization; must run after transactions.
12. **investments** — depends on identity, accounts, transactions; must run after accounts and transactions.

Cross-domain integration tests (Section 4 gaps) should be run after all 12 unit-domain suites pass.

---

## 6. Issues Found

The following factual errors, contradictions, or structural problems were found during the audit.

| # | File | Section / Scenario | Issue | Suggested Fix |
|---|------|--------------------|-------|---------------|
| 1 | statements-test-guide.md | Domain Scope table | `Events consumed: None` — but statements Scenario 1 Step 9 refers to "outbox poller dispatches `ExtractionCompleted` to `transactions` domain handler", implying a consumer exists. The statement domain is the *producer*, not consumer — the table is correct. However, the scenario narrative says "domain is triggered by HTTP upload, not domain events" which is accurate but slightly confusing alongside the outbox flow. | Clarify prose: "The statements domain consumes no events from other domains; it is triggered by HTTP upload only. It produces events consumed by other domains." |
| 2 | accounts-test-guide.md | Scenario 4 "Side effects" | States "After the outbox poller runs, the `investments` domain sets `is_active = false` on all `sip_registrations`..." This is correct per the domain doc, but the accounts test guide has no step or assertion to verify this actually happened — it is a documentation claim only. | Add a step: after the outbox poller runs (or wait 5 s), query `sip_registrations WHERE bank_account_id = <this account>` and assert `is_active = false` for any rows that matched. |
| 3 | transactions-test-guide.md | Scenario 9 "Source slice" reference | References `docs/slices/15-add-transaction-manually.md (event-driven path)` — this slice is about manual entry, not event-driven creation from statements. The correct source slice is `docs/domains/transactions.md` (Events Subscribed section). | Change source slice reference to `docs/domains/transactions.md — Events Subscribed` or add a slice specifically for the `ExtractionCompleted` → transaction creation path. |
| 4 | categorization-test-guide.md | Scenario 3, Edge Case table | Two edge cases are marked TODO for `amount_gte`, `amount_lte`, and `source_account_id` conditions: "TODO: the domain doc lists only `pattern` and `match_type`..." — after reading `docs/domains/categorization.md`, these columns do **not appear** in the `categorization_rules` table definition. The task description referenced these, but the canonical domain doc does not include them. | Remove or annotate these edge cases as "feature not yet implemented / not in current schema"; do not write tests for columns that do not exist. |
| 5 | earnings-test-guide.md | Scenario 2 Step 4 | Step says `POST /earnings/classify/{transaction_id}` with body `{ "classification": "freelance", "source_type": "freelance" }` — the field names `classification` and `source_type` may be redundant (both carry the same information). The actual API contract is flagged as undocumented in Coverage Gaps. | Confirm the endpoint schema from `src/elixir/domains/earnings/api.py` before writing tests; the request body fields are speculative. |
| 6 | budgets-test-guide.md | TODO list | The TODO list items are not numbered with `[ ]` checkboxes like the other 11 domain test guides — they use bullet points. This makes them harder to parse and count. | Reformat the TODO list to use `- [ ]` checkbox syntax consistent with all other domain test guides. |
| 7 | investments-test-guide.md | Scenario 4 Step 5 | `GET /investments/sip/confirm?sip_registration_id=<id>&transaction_id=<id>` — this is a GET with query parameters for a "confirmation screen"; in a standard REST API, a confirmation screen data fetch would typically be `GET /investments/sip/{sip_registration_id}/pending-match` or similar. The exact endpoint path is not confirmed. | Mark as TODO: confirm endpoint path from `src/elixir/domains/investments/api.py`. |
| 8 | notifications-test-guide.md | Scenario 2 | Lists `metadata.route = "/investments/sip/confirm"` for `SIPDetected` notifications, but `docs/domains/notifications.md` specifies `metadata: {"route": "/investments/sip/confirm", "transaction_id": "{tx_id}", "sip_id": "{sip_id}"}` — the key name in the notifications domain doc is `"sip_id"` while the notifications test-guide Scenario 5 asserts `metadata->>'sip_id' = :sip_id`. These are consistent. No error here, but worth noting the assertion in Scenario 2 does not include the `sip_id` key check — it should. | Add `metadata.sip_id` assertion to Scenario 2 for the `SIPDetected` type. |
| 9 | fx-test-guide.md | Domain Scope table | States `Events consumed: None` and `Events published: None`. However, the fx domain test guide Coverage Gaps notes that `FXRateRefreshWorkflow` queries `bank_accounts`, `credit_cards`, and `instruments` inside an activity. This is a cross-domain read that should use a view or be listed as an inter-domain dependency. | Add a note in the fx domain scope: "Reads `bank_accounts.currency`, `credit_cards.currency`, and `instruments.currency` inside the `FXRateRefreshWorkflow` activity (not a view dependency — direct table names are used; verify this is only inside a Temporal activity, not workflow code)." |
| 10 | All 12 guides | Coverage Gaps / TODO | None of the 12 test guides has a linked Playwright test file path. Every guide has a TODO item to "Add Playwright E2E tests once endpoint contracts are confirmed." This means zero actual executable tests currently exist. | After endpoint contract confirmation (all the API TODO items), scaffold Playwright test files at the paths recommended in the frontend development guidelines. |
| 11 | import_-test-guide.md | Events listed | `ImportBatchReady` event is listed in the Domain Scope under "Events published". However, per `docs/domains/import_.md`, `ImportBatchReady` is published *after parsing/categorisation*, and `ImportCompleted` is published *after transactions domain has processed the batch*. The test guide Scenario 1 assertion says "Events: `ImportBatchReady` outbox row was written and processed" — the test cannot verify "processed" without checking `transactions` rows, which is a cross-domain assertion not in the import_ test guide. | Add a cross-domain assertion or a note: "Verify `ImportBatchReady` was consumed by querying `transactions` rows with `source = 'bulk_import'` — see transactions-test-guide.md Scenario 10." |
