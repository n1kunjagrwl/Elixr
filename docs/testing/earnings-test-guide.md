# earnings — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

From the user's perspective, the earnings domain answers the question "what do I actually earn?". Most bank credits are not income — a friend paying back dinner looks identical in a statement to a small freelance payment. The domain automatically classifies high-confidence credits (salary keywords, recurring monthly amounts, known employer patterns) as income, asks the user to decide when a credit is ambiguous, and lets the user log income that never appears in a bank statement at all (cash, foreign wires). Earnings are grouped by source type (salary, freelance, rental, dividend, interest, business, other) and optionally by named earning sources so the user can answer questions like "how much did I earn from freelancing this year versus my salary?".

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `earnings`, `earning_sources`, `outbox` |
| Events published | `EarningRecorded`, `EarningClassificationNeeded` |
| Events consumed | `TransactionCreated` (from `transactions` domain) |
| Temporal workflows | None (heuristic classification is synchronous in the `TransactionCreated` handler) |
| Slices covered | 22, 23, 38, 39, 45 |

---

## Test Scenarios

---

### Scenario 1: Automatic income detection from a bank statement credit

**Source slice**: `docs/slices/` — event-driven path described in `docs/domains/earnings.md` (Events Subscribed)
**Business intent**: When a credit transaction is created and the heuristics score it as income with confidence ≥ 0.85, the earnings domain automatically creates an `earnings` record linked to the source transaction.
**Domains involved**: earnings, transactions

#### Preconditions
- User is authenticated.
- User has an existing `earning_sources` entry with a historical salary credit pattern (same amount ±5%, similar day of month) — OR — the credit description contains a salary keyword such as `SALARY`, `NEFT`, or a known employer name, producing a heuristic score ≥ 0.85.
- No `earnings` row already exists for the target `transaction_id` (idempotency baseline).

#### Steps
1. POST a new credit transaction via `POST /transactions` (or trigger via statement upload) with an amount and description that matches the high-confidence salary heuristic (e.g., amount = ₹80,000, description = "SALARY THINK41 NEFT").
2. Allow the `TransactionCreated` event to be dispatched through the outbox poller (≤ 2-second polling cycle).
3. Query `GET /api/v1/earnings/` for the test user.

#### Assertions
- **DB**: A row exists in `earnings` where `transaction_id = <new_transaction_id>`, `source_type = 'salary'`, `amount = 80000`, `currency = 'INR'`, and `transaction_id IS NOT NULL`.
- **API response**: `GET /api/v1/earnings/` returns the new record; `transaction_id` is populated (not null); the response field indicates auto-detected origin.
- **Events**: One `EarningRecorded` event row exists in the `outbox` table for the `earning_id` just created, with `event_type = 'earnings.EarningRecorded'`.
- **Side effects**: No `EarningClassificationNeeded` event is published — the classification was resolved automatically.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Handler called twice for the same `transaction_id` (at-least-once delivery) | Second invocation is a no-op — no duplicate `earnings` row is created; idempotency check on `transaction_id` prevents double-insertion | [ ] |
| Credit is a self-transfer (`transaction.type = 'transfer'`) | Handler skips entirely; no `earnings` row created; no event published | [ ] |
| Credit is a debit (non-credit type) | Handler skips entirely | [ ] |
| Description matches a known peer name from `peer_contacts_public` view | Heuristic score skews toward peer repayment; if score ≥ 0.85 for repayment, no `earnings` row is created and no `EarningClassificationNeeded` is published either — peers domain handles it | [ ] |

---

### Scenario 2: Ambiguous credit triggers user classification prompt

**Source slice**: `docs/domains/earnings.md` (heuristic handler, ambiguous branch); `docs/business-intent/earnings.md`
**Business intent**: When the system cannot confidently classify a credit as income or a peer repayment (score < 0.85 for both), it publishes `EarningClassificationNeeded` so the user can decide.
**Domains involved**: earnings, transactions, notifications

#### Preconditions
- User is authenticated.
- The incoming credit has an amount and description that do not match any salary keyword, do not match any `earning_sources` pattern, and do not confidently match any peer contact name — producing an ambiguous score (< 0.85 for income, < 0.85 for peer repayment).

#### Steps
1. POST a credit transaction with an ambiguous description (e.g., amount = ₹1,500, description = "UPI/Rahul").
2. Allow the `TransactionCreated` handler to run via the outbox poller.
3. Check the outbox for the published event.
4. Submit a classification via `POST /api/v1/earnings/classify/{transaction_id}` with body `{ "classification": "freelance", "source_type": "freelance" }`. Expect response `{"status": "classified"}`.
5. Query `GET /api/v1/earnings/` for the test user.

#### Assertions
- **DB (after step 2)**: No `earnings` row exists for this `transaction_id` yet.
- **Events (after step 2)**: An `EarningClassificationNeeded` event row exists in the `outbox` for this `transaction_id`, `user_id`, with `amount` and `description` fields populated.
- **DB (after step 4)**: An `earnings` row is created with `transaction_id = <id>`, `source_type = 'freelance'`, `transaction_id IS NOT NULL`.
- **API response (after step 5)**: The record appears in `GET /api/v1/earnings/` with a non-null `transaction_id`.
- **Side effects**: A notification (consumed from `EarningClassificationNeeded` by the notifications domain) is created for the user — verify via `GET /notifications`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User classifies as "peer repayment" (not income) | No `earnings` row is created; the `peers` domain handles the repayment; `EarningClassificationNeeded` is resolved | [ ] |
| User classifies as "ignore" | No `earnings` row created; credit is acknowledged and will not prompt again | [ ] |
| User classifies as "peer repayment" and optionally links to an existing peer balance | Peer balance settlement is recorded in the `peers` domain; see inconsistency [3.7] for known gap in documentation of this path | [ ] |
| Classification endpoint called twice for same `transaction_id` | Second call should be idempotent — return 200/409 without creating a duplicate `earnings` row; TODO: confirm exact behaviour | [ ] |

---

### Scenario 3: Manual earning creation (no linked bank transaction)

**Source slice**: `docs/slices/22-add-manual-earning.md`
**Business intent**: Users can log income that has no corresponding bank transaction (cash, foreign wire not yet in a statement) by entering amount, date, source type, and an optional source label or named source.
**Domains involved**: earnings

#### Preconditions
- User is authenticated.
- Optional: User has at least one active `earning_sources` entry (to test the `source_id` path); tests without any sources exercise the `source_label` free-text path.

#### Steps
1. `POST /api/v1/earnings/` with body:
   ```json
   {
     "amount": 25000,
     "currency": "INR",
     "date": "2026-05-10",
     "source_type": "freelance",
     "source_label": "Consulting - Acme Corp",
     "notes": "Invoice #001"
   }
   ```
2. Query `GET /api/v1/earnings/{earning_id}` to inspect the created record.

#### Assertions
- **DB**: A row exists in `earnings` with `transaction_id = NULL`, `source_type = 'freelance'`, `amount = 25000`, `currency = 'INR'`, `source_label = 'Consulting - Acme Corp'`, `notes = 'Invoice #001'`.
- **API response**: HTTP 201; the returned record has `transaction_id: null`; a "Manual" badge / origin indicator is present in the response.
- **Events**: One `EarningRecorded` event row exists in the `outbox` for the new `earning_id`.
- **Side effects**: The record appears immediately in `GET /api/v1/earnings/` and contributes to the monthly income aggregation for May 2026.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `source_id` provided and resolves to an active `earning_sources` entry | `earnings.source_id` is set; `source_label` is optional but still stored if provided | [ ] |
| No `earning_sources` exist yet | Request succeeds using `source_label` free-text only; `source_id = NULL` | [ ] |
| Non-INR currency (e.g., `"currency": "USD"`) | Row stored with `currency = 'USD'` and the entered `amount`; `fx.convert()` is called at display/aggregation time — raw amount preserved in DB | [ ] |
| **Duplicate manual entry risk**: Same `amount`, `date`, and `source_type` submitted twice | Both rows are created successfully — no fingerprint deduplication applies to manual earnings; second submission is not blocked; see Known Inconsistency [3.8] | [ ] |
| Missing required field `amount` | HTTP 422 Unprocessable Entity | [ ] |
| Missing required field `source_type` | HTTP 422 Unprocessable Entity | [ ] |
| Both `source_id` and `source_label` are absent | HTTP 422; service layer must require at least one of the two | [ ] |

---

### Scenario 4: Earning source management (create, edit, deactivate)

**Source slice**: `docs/slices/23-manage-earning-sources.md`
**Business intent**: Users create named income source labels (e.g., "Think41 Salary") to organise income by origin; sources feed the heuristic matching for auto-classification and appear in the manual earning dropdown.
**Domains involved**: earnings

#### Preconditions
- User is authenticated.

#### Steps — Create
1. `POST /api/v1/earnings/sources` with body `{ "name": "Think41 Salary", "type": "salary" }`.
2. Query `GET /api/v1/earnings/sources` to confirm the source appears with `is_active = true`.
3. Verify the new source appears in the dropdown when creating a manual earning (query the sources list endpoint filtered to active entries).

#### Steps — Edit
4. `PATCH /api/v1/earnings/sources/{source_id}` with body `{ "name": "Think41 — Engineering Salary", "type": "salary" }`.
5. Query `GET /api/v1/earnings/sources/{source_id}` to confirm the name is updated.
6. Query `GET /api/v1/earnings/` and confirm that existing `earnings` rows linked via `source_id` now display the updated source name in the UI (source_type values on individual rows are unchanged — they are snapshots).

#### Steps — Deactivate
7. `DELETE /api/v1/earnings/sources/{source_id}` → expect `204 No Content`. This is a soft-deactivate — the row is not hard-deleted; `is_active` is set to `false`.
8. Query `GET /api/v1/earnings/sources?active_only=true` — the deactivated source must not appear.
9. Attempt to create a new manual earning and confirm the deactivated source does not appear in the dropdown.
10. Query existing `earnings` rows that reference this `source_id` — they must still be retrievable and still show the source name (soft delete; data is preserved).

#### Assertions
- **DB (create)**: `earning_sources` row exists with `is_active = true`, correct `name` and `type`.
- **DB (edit)**: `earning_sources.name` updated; `updated_at` refreshed; existing linked `earnings.source_type` values unchanged.
- **DB (deactivate)**: `earning_sources.is_active = false`; no `earnings` rows are orphaned or altered.
- **API response**: No events are published on any source operation (create, edit, deactivate all fire no outbox entries).
- **Side effects**: Active sources list used by heuristic matching reflects the change on next `TransactionCreated` event.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Two sources with the same name and type | Both are created; no uniqueness constraint on `(name, type)` — allowed by design | [ ] |
| Source referenced by existing earnings is deactivated | Existing earnings retain `source_id`; `source_type` ensures aggregation continues; deactivated source not shown in dropdown | [ ] |
| Source deleted (hard delete, if supported) | `earnings.source_id` becomes an orphaned nullable foreign key (no PG FK constraint by design); existing earnings display `source_label` as fallback | [ ] |
| Creating a source with an invalid `type` value | HTTP 422 | [ ] |

---

### Scenario 5: View earnings dashboard with aggregation and period selection

**Source slice**: `docs/slices/38-view-earnings-dashboard.md`
**Business intent**: Users see their total income for a time period broken down by source type, with auto-detected and manually entered earnings shown together; foreign-currency earnings are converted to INR for aggregated totals.
**Domains involved**: earnings, fx

#### Preconditions
- User is authenticated.
- At least one `earnings` row exists for the current calendar month (mix of auto-detected and manual preferred to exercise both badge types).
- At least one earning has a non-INR currency to exercise the `fx.convert()` path.

#### Steps
1. `GET /api/v1/earnings/dashboard` (or equivalent endpoint) for the default period (current month).
2. Inspect the response for the monthly total, per-source-type breakdown, and individual row badge indicators.
3. Change the period to "This Year" and re-query.
4. Change the period to a custom date range that spans no earnings.

#### Assertions
- **API response (step 1)**:
  - `total` field equals the sum of all `earnings.amount` values (non-INR converted via `fx.convert()`) for the current month.
  - Response contains a `by_source_type` array grouping earnings with per-group totals, counts, and percentage shares.
  - Groups with zero earnings in the period are absent from the response.
  - Each individual earning row includes an `origin` field: `"bank"` where `transaction_id IS NOT NULL`, `"manual"` where `transaction_id IS NULL`.
- **API response (step 3)**: Total and breakdowns recomputed for the year-to-date range.
- **API response (step 4)**: `total = 0`, empty breakdowns, appropriate empty-state message.
- **DB**: No write operations occur on any `GET` — dashboard is read-only.
- **Events**: None published.
- **Side effects**: If a non-INR rate is more than 24 hours old, the response includes a `rate_note` or equivalent field with the fetched_at timestamp.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| All earnings are INR | `fx.convert()` is never called; no rate-staleness indicator in response | [ ] |
| FX rate unavailable for a non-INR earning currency | Affected rows shown in original currency with a warning indicator; aggregate total is computed from convertible rows only; response footer notes "N earning(s) in {currency} excluded from total — rate unavailable" | [ ] |
| Auto-detected earning where user later edited `source_type` | Record appears in the new `source_type` group, not the original heuristic group — aggregation reflects the stored value | [ ] |
| `source_id` on an earning points to a deactivated source | Earning still displayed; `source_label` (stored at creation) used for display label | [ ] |
| No earnings in any period | Dashboard shows ₹0 total and empty state message; period selector remains active | [ ] |

---

### Scenario 6: Edit an existing earnings record

**Source slice**: `docs/slices/39-edit-earning.md`
**Business intent**: Users can correct any earning record — whether auto-detected or manually entered — by changing source type, linked source, amount, currency, date, or notes; no downstream events are triggered.
**Domains involved**: earnings

#### Preconditions
- User is authenticated.
- An `earnings` row exists for this user (test both an auto-detected row with `transaction_id IS NOT NULL` and a manual row with `transaction_id IS NULL`).

#### Steps
1. `GET /api/v1/earnings/{earning_id}` to capture current values.
2. `PATCH /api/v1/earnings/{earning_id}` changing `source_type` from `'salary'` to `'freelance'`.
3. Query `GET /api/v1/earnings/{earning_id}` to confirm the update.
4. Query `GET /api/v1/earnings/dashboard` to confirm the record now appears in the `freelance` group, not `salary`.
5. For an auto-detected earning: confirm the `transaction_id` link is preserved after the edit.
6. Attempt to clear `source_id` without providing a `source_label`.

#### Assertions
- **DB**: `earnings.source_type = 'freelance'`; `updated_at` is newer than before the edit; `transaction_id` unchanged for auto-detected earnings.
- **API response (step 3)**: Updated fields reflected; `transaction_id` (if set) still present.
- **API response (step 4)**: Earning appears in `freelance` group; no longer in `salary` group.
- **Events**: No `EarningRecorded` or any other event is published — editing an earning is silent by design.
- **Side effects**: No re-classification, no budget recalculation, no downstream domain reactions.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Clearing `source_id` with no `source_label` provided | HTTP 422 — at least one of `source_id` or `source_label` must be set | [ ] |
| Editing `amount` on an auto-detected earning | `earnings.amount` updated; the linked `transactions.amount` is not changed; the two values may now differ (intended: net vs. gross) | [ ] |
| Saving with no changed fields | HTTP 200; `updated_at` refreshed; no visible change otherwise | [ ] |
| Changing `date` to a different month | Earning moves to the new month in dashboard aggregation on next load | [ ] |
| User does not own the `earning_id` (wrong `user_id`) | HTTP 404 (not 403 — do not reveal existence of another user's records) | [ ] |

---

### Scenario 7: Filter earnings by source type, named source, and date range

**Source slice**: `docs/slices/45-filter-earnings-by-source.md`
**Business intent**: Users can narrow the earnings list to a specific income type or named source to answer questions like "how much did I earn from freelancing this year?" or "what has Acme Corp paid me since January?".
**Domains involved**: earnings, fx

#### Preconditions
- User is authenticated.
- At least three `earnings` rows exist with different `source_type` values (e.g., `salary`, `freelance`, `rental`).
- At least one `earnings` row has a `source_id` linking to a named `earning_sources` entry.
- At least one `earnings` row has `source_id = NULL` (only a `source_label`).
- Rows span at least two calendar months to test date range filtering.

#### Steps
1. `GET /api/v1/earnings/?source_type=freelance` — single source type filter.
2. `GET /api/v1/earnings/?source_type=freelance&source_type=salary` — multi-select source type filter.
3. `GET /api/v1/earnings/?source_id={source_id}` — filter by named earning source.
4. `GET /api/v1/earnings/?source_type=freelance&date_from=2026-01-01&date_to=2026-12-31` — combined filter (type + date range).
5. `GET /api/v1/earnings/?source_id={source_id}` where some matching rows have `source_id = NULL` (free-text only entries).
6. Clear all filters and confirm the full unfiltered list is returned.

#### Assertions
- **API response (step 1)**: All returned rows have `source_type = 'freelance'`; rows of other types are absent; response header total equals the sum of freelance earnings.
- **API response (step 2)**: Rows have `source_type IN ('freelance', 'salary')`; no rental/other rows.
- **API response (step 3)**: All returned rows have `source_id = {source_id}`; rows with `source_id = NULL` are excluded even if their `source_label` matches the source name textually.
- **API response (step 4)**: SQL equivalent of `WHERE source_type = 'freelance' AND date BETWEEN '2026-01-01' AND '2026-12-31'`; combined total shown; page resets to page 1.
- **API response (step 5)**: Only rows with matching `source_id` returned; free-text-only rows with matching `source_label` are excluded (known limitation — see edge cases).
- **DB**: All filter queries are read-only; no rows modified.
- **Events**: None published.
- **Side effects**: Non-INR amounts in the filtered set are converted via `fx.convert()` for the summary total; staleness note shown if rate > 24 hours old.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| No earnings match the combined filters | HTTP 200 with empty list; empty-state message; all filter chips remain visible | [ ] |
| Deactivated earning source referenced by existing rows | Deactivated source hidden from filter dropdown for new selections; existing earnings linked to it are still returned when filtering by that `source_id`; source name shown with "(Inactive)" tag | [ ] |
| Large result set — pagination | Summary totals (count and amount) computed server-side over the full filtered set; list view paginates; total in header is always accurate even before all pages are loaded | [ ] |
| FX rate unavailable and all filtered rows are non-INR | Total shown as "Total unavailable — FX rates missing"; individual rows still displayed in original currencies | [ ] |
| `source_label` matches the name of a named source but `source_id` is NULL | Row is excluded from named-source filter results — this is a known limitation of the two-path labelling design; user must search via unfiltered list | [ ] |
| `source_label = NULL` and `source_id = NULL` on a row (malformed data) | Row displays "Unlabelled" as fallback; does not crash the filter query | [ ] |

---

## Known Inconsistencies

- **[3.7]** Ambiguous credit classified as peer repayment can optionally link to an existing peer balance entry to record a settlement in the `peers` domain simultaneously. The earnings business intent (`docs/business-intent/earnings.md`) does not describe what happens in the peers domain when the user selects "peer repayment" in the classification flow. Tests for the ambiguous-credit classification path (Scenario 2) should include a case where the user selects "peer repayment" and optionally links it to an open balance — but the exact API contract and whether `peer_balances` is updated atomically with the earnings classification decision is not fully documented. Mark this test case as TODO until the cross-domain behaviour is confirmed.

- **[3.8]** Manual earnings have no deduplication. Unlike bank transactions (which use a SHA-256 fingerprint to prevent double-import), manually entered earnings (`transaction_id = NULL`) have no uniqueness constraint on `(user_id, amount, date, source_type)`. Two identical submissions are both accepted and both persist. The UI may warn if an earning with the same amount and date already exists, but does not block submission. Scenario 3 includes a specific edge case for this: submitting the same manual earning twice must result in two separate `earnings` rows. This is the intended (if risky) behaviour and must be asserted as such — do not treat it as a test failure.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| The `POST /api/v1/earnings/classify/{transaction_id}` endpoint contract is partially confirmed: it accepts a `ClassifyTransactionRequest` body and returns `{"status": "classified"}` on success (HTTP 200). What happens if the transaction has already been classified (idempotency) and the full error response shape are still unconfirmed. | `docs/domains/earnings.md` — handler mentions the endpoint exists but does not specify the API contract fully | Write a slice or API contract doc for the error paths of the classification endpoint and add them to Scenario 2 |
| The optional peer-balance linking step when classifying an ambiguous credit as a peer repayment ([3.7]) has no documented API contract or cross-domain atomicity guarantee | `docs/business-intent/INCONSISTENCIES.md` §3.7; `docs/slices/` (slice 21 referenced but not listed in the source slices for this guide) | Read `docs/slices/21-classify-ambiguous-credit.md` and reconcile with earnings domain events; add a cross-domain scenario |
| Heuristic scoring logic (thresholds, keyword lists, day-of-month window for salary matching) is described in prose but not specified precisely enough to write deterministic test fixtures | `docs/domains/earnings.md` — Events Subscribed handler | Add a `docs/testing/earnings-heuristic-fixtures.md` with canonical test cases for score ≥ 0.85 (income), score ≥ 0.85 (peer), and ambiguous ranges |
| `GET /api/v1/earnings/dashboard` endpoint path and response schema are not fully confirmed — the slice describes the UI behaviour but the API contract is implicit | `docs/slices/38-view-earnings-dashboard.md` | Confirm response shape from the `api.py` implementation before writing Scenario 5 assertions |
| Filter endpoint query parameter names (`source_type`, `source_id`, `date_from`, `date_to`) are confirmed from the API implementation but multi-value `source_type` handling (repeated param vs comma-separated) should be verified | `docs/slices/45-filter-earnings-by-source.md` | Confirm multi-value parameter handling from implementation |
| No test scenario for the "view all earning sources and their totals" summary view mentioned as a missing flow in INCONSISTENCIES §4 | `docs/business-intent/INCONSISTENCIES.md` §4 (missing slices table) | Determine if this view is in scope; if so, add a Scenario 8 |
| The `fx` domain's `FXRateUnavailableError` handling path in Scenarios 5 and 7 requires a way to force a missing FX rate in tests | `docs/slices/38-view-earnings-dashboard.md` and `docs/slices/45-filter-earnings-by-source.md` edge cases | Add test fixture or mock strategy for `fx.convert()` failure injection |

---

## TODO

- [ ] Read `docs/slices/21-classify-ambiguous-credit.md` and extend Scenario 2 with the full classification flow, including the peer-balance linking sub-path ([3.7]).
- ✅ Resolved — Confirmed API endpoint paths from implementation: `POST /api/v1/earnings/`, `GET /api/v1/earnings/`, `PATCH /api/v1/earnings/{earning_id}`, `POST /api/v1/earnings/classify/{transaction_id}` (returns `{"status": "classified"}`), `GET /api/v1/earnings/sources`, `POST /api/v1/earnings/sources`, `PATCH /api/v1/earnings/sources/{source_id}`, `DELETE /api/v1/earnings/sources/{source_id}` (soft-deactivate → 204). `GET /api/v1/earnings/dashboard` path is assumed from implementation convention; verify response schema before finalising Scenario 5.
- [ ] Determine whether the outbox poller (2-second cycle) requires test helpers to advance time or flush the outbox synchronously in the test environment — if not, Scenarios 1 and 2 may need a `wait_for` step or a direct event dispatch call.
- ✅ Resolved — `earning_sources` deactivation is a soft-delete via `DELETE /api/v1/earnings/sources/{source_id}` → 204. The endpoint sets `is_active = false` and preserves the row and all linked earnings. Hard-delete is not supported via the API. Scenario 4 has been updated accordingly. The edge case row "Source deleted (hard delete, if supported)" in Scenario 4 remains as a known gap — a hard-delete path does not exist at the API level.
- [ ] Add Playwright E2E counterparts for Scenarios 3 (manual earning form), 4 (source management UI), 5 (dashboard renders), and 7 (filter panel) once the frontend screens exist.
- [ ] Verify that the `peer_contacts_public` SQL view (queried by the earnings heuristic handler to detect peer names in credit descriptions) is present and populated in the test database setup — missing this view will cause Scenario 1 and 2 handlers to error.
