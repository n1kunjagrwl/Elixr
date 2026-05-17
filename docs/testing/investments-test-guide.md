# investments — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The investments domain tracks everything a user owns across stocks, mutual funds, ETFs, Fixed Deposits, PPF, bonds, NPS, Sovereign Gold Bonds, physical gold, US stocks, and cryptocurrency — giving them a single portfolio view with current market values, gain/loss figures, and historical growth charts. Live prices are fetched every 15 minutes during market hours for market-traded instruments; non-market instruments (FDs, PPF, bonds) are valued daily using financial formulas. When a bank statement debit matches a registered SIP pattern, the user is notified and asked to confirm the link, keeping the portfolio up-to-date without manual bookkeeping.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `instruments`, `holdings`, `sip_registrations`, `valuation_snapshots`, `fd_details`, `outbox` |
| Events published | `SIPDetected`, `SIPLinked`, `ValuationUpdated` |
| Events consumed | `TransactionCreated` (from `transactions`), `AccountRemoved` (from `accounts`) |
| Temporal workflows | `MarketPriceFetchWorkflow` (every 15 min during market hours; every 6 h otherwise), `CalculatedValuationWorkflow` (daily 00:30 IST) |
| Slices covered | 27, 28, 29, 30, 31, 32, 41 |

---

## Test Scenarios

---

### Scenario 1: Add a Market-Traded Holding (Stock / MF / ETF)

**Source slice**: `docs/slices/27-add-investment-holding.md`
**Business intent**: A user searches for a market-traded instrument, enters units and average cost, and the holding appears in the portfolio immediately with a "Valuation pending" state.
**Domains involved**: investments

#### Preconditions
- User is authenticated.
- The instrument (e.g. `INFY`, type `stock`) exists in the `instruments` table, or will be created during the flow.
- No existing `holdings` row for this user + instrument.

#### Steps
1. `POST /api/v1/investments/holdings` with body:
   ```json
   {
     "instrument_id": "<uuid>",
     "units": 10,
     "avg_cost_per_unit": 1500.00,
     "total_invested": 15000.00,
     "as_of_date": "2026-05-17"
   }
   ```
2. Verify the API response.
3. Query the `holdings` table directly to verify the stored row.
4. `GET /api/v1/investments/holdings` and `GET /api/v1/investments/summary` to confirm the holding appears.

#### Assertions
- **DB**: A `holdings` row exists with `user_id`, `instrument_id`, `units = 10`, `avg_cost_per_unit = 1500.00`, `total_invested = 15000.00`, `current_value = NULL`, `current_price = NULL`, `last_valued_at = NULL`.
- **API response**: HTTP 201; response body contains `holding_id`, `instrument_id`, `units`, `avg_cost_per_unit`, `total_invested`; `current_value` is `null`; a `valuation_status = "pending"` (or equivalent) indicator is present.
- **Events**: No event published at creation time; `ValuationUpdated` is published only after the next workflow run.
- **Side effects**: If the instrument did not exist, a new `instruments` row has been created with the correct `type` and `data_source`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Duplicate holding (same `user_id` + `instrument_id`) | HTTP 409 — "You already hold this instrument. Edit the existing holding instead." | [ ] |
| `units` = 0 or negative | HTTP 422 with field-level validation error on `units` | [ ] |
| `avg_cost_per_unit` = 0 or negative | HTTP 422 with field-level validation error | [ ] |
| `total_invested` differs from `units × avg_cost_per_unit` by > 0.5% | HTTP 201 — holding saved; response body includes a reconciliation warning flag | [ ] |
| Unsupported `currency` value | HTTP 422 | [ ] |
| Two concurrent requests for the same new ticker (race on `instruments` insert) | Both requests succeed; second insert retries SELECT and reuses existing `instruments` row; no 500 error | [ ] |

---

### Scenario 2: Add a Fixed Deposit

**Source slice**: `docs/slices/28-add-fixed-deposit.md`
**Business intent**: A user registers an FD with principal, interest rate, tenure, and compounding frequency; the system stores the FD details and immediately shows the principal as the invested amount while scheduling daily valuation.
**Domains involved**: investments

#### Preconditions
- User is authenticated.
- No existing `holdings` row for an FD instrument with the same name for this user (no unique constraint on FD name — duplicates are possible; see edge cases).

#### Steps
1. `POST /api/v1/investments/holdings` with body for FD (uses the standard holdings endpoint; FD-specific details are passed after creation via `POST /api/v1/investments/holdings/{holding_id}/fd`):
   ```json
   {
     "type": "fd",
     "name": "SBI FD — Savings",
     "principal": 100000.00,
     "rate_percent": 7.0,
     "start_date": "2025-01-01",
     "tenure_days": 365,
     "compounding": "quarterly"
   }
   ```
2. Verify API response.
3. Query the `holdings` table and `fd_details` table directly.
4. `GET /api/v1/investments/holdings` and `GET /api/v1/investments/summary` to confirm the FD card appears.

#### Assertions
- **DB**: A `holdings` row exists with `units = 1`, `avg_cost_per_unit = 100000.00`, `total_invested = 100000.00`, `current_value = NULL`, `last_valued_at = NULL`.
- **DB**: A `fd_details` row linked to the `holding_id` exists with `principal = 100000.00`, `rate_percent = 7.0`, `tenure_days = 365`, `start_date = 2025-01-01`, `maturity_date = 2026-01-01`, `compounding = 'quarterly'`, and a populated `maturity_amount` (computed as `100000 × (1 + 0.07/4)^4 ≈ 107185.90`).
- **API response**: HTTP 201; response body contains `holding_id`, `principal`, `maturity_date`, `maturity_amount`.
- **Events**: None at creation time.
- **Side effects**: An `instruments` row with `type = 'fd'` and `name = 'SBI FD — Savings'` exists (reused if it pre-existed for another user).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `rate_percent = 0` | HTTP 422 — "An FD with 0% interest is not valid." | [ ] |
| `tenure_days = 0` | HTTP 422 | [ ] |
| `start_date` in the past such that `maturity_date < today` (backdated FD) | HTTP 201 — FD created; response includes "This FD has already matured" indicator; `CalculatedValuationWorkflow` caps value at `maturity_amount` | [ ] |
| Same FD name entered twice by the same user | HTTP 201 for both — no automatic deduplication; two `holdings` rows created with different IDs referencing the same `instruments` row | [ ] |

---

### Scenario 3: Register a SIP

**Source slice**: `docs/slices/29-register-sip.md`
**Business intent**: A user registers a recurring SIP debit so future matching debits are automatically detected and linked to the investment holding.
**Domains involved**: investments, accounts

#### Preconditions
- User is authenticated.
- At least one `bank_accounts` row exists for this user (`is_active = true`).
- A `holdings` row exists for the target instrument (type `mf`, `stock`, or `etf`).

#### Steps
1. `POST /api/v1/investments/sip` with body:
   ```json
   {
     "instrument_id": "<uuid>",
     "amount": 5000.00,
     "frequency": "monthly",
     "debit_day": 7,
     "bank_account_id": "<uuid>"
   }
   ```
2. Verify API response.
3. Query the `sip_registrations` table or `GET /api/v1/investments/sip` to confirm the new SIP appears.
4. `GET /api/v1/investments/holdings` to confirm the "SIP Active" badge is reflected on the relevant holding.

#### Assertions
- **DB**: A `sip_registrations` row exists with `user_id`, `instrument_id`, `amount = 5000.00`, `frequency = 'monthly'`, `debit_day = 7`, `bank_account_id`, `is_active = true`.
- **API response**: HTTP 201; response body contains `sip_id` (SIPResponse) and a success message confirming the SIP is registered.
- **Events**: None at registration time; `SIPDetected` is published later when a matching `TransactionCreated` event arrives.
- **Side effects**: The holding's detail endpoint reflects a "SIP Active" badge (i.e. a linked `sip_registrations` row with `is_active = true`).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| No bank accounts linked | HTTP 400 — form blocked; "Register SIP" action is unavailable | [ ] |
| `debit_day` set to 29, 30, or 31 for monthly frequency | HTTP 422 — debit days 29–31 not allowed for monthly/quarterly SIPs | [ ] |
| `amount < 100` | HTTP 422 — amount below minimum plausible SIP threshold | [ ] |
| Duplicate SIP (same `user_id` + `instrument_id` + `bank_account_id` + `frequency` + `debit_day`, `is_active = true`) | HTTP 409 — "An active SIP for this instrument and account already exists." | [ ] |
| `AccountRemoved` event published for the linked `bank_account_id` | `sip_registrations.is_active` is set to `false`; no notification is sent to the user (see Known Inconsistencies §1.5) | [ ] |

---

### Scenario 4: SIP Auto-Detection from Statement Import (with `waitForSignal` confirmation step)

**Source slice**: `docs/slices/30-confirm-sip-detection.md`
**Business intent**: When a bank statement debit matches a registered SIP, the system detects the match and pauses for user confirmation before linking the transaction to the holding.
**Domains involved**: investments, transactions, notifications

#### Preconditions
- User is authenticated.
- An active `sip_registrations` row exists: `amount = 5000.00`, `frequency = 'monthly'`, `debit_day = 7`, `bank_account_id = <acct-uuid>`, `is_active = true`.
- A debit transaction is created (via statement import, CSV import, or manual entry) with: amount within ±2% of 5000.00 (e.g. 4950.00–5100.00), date within ±3 days of the 7th of the month, `bank_account_id` matching the registered account.

#### Steps
1. Simulate or trigger a `TransactionCreated` event for the matching debit transaction (e.g. by importing a statement containing this debit, or via direct event injection in the test harness).
2. Wait for the investments domain's `TransactionCreated` handler to evaluate the SIP match.
3. Verify that a `SIPDetected` event is published to the outbox and dispatched.
4. Verify that the notifications domain creates a `notifications` row of type `SIPDetected`.
5. Call the notification-detail endpoint to fetch the confirmation screen data (include `sip_id` and `transaction_id` from the `SIPDetected` notification metadata).
6. Submit confirmation: `POST /api/v1/investments/sip/{sip_id}/confirm` with body `{ "transaction_id": "<id>" }`. Expect response `{"status": "confirmed"}`.
7. Verify that `SIPLinked` event is published.

#### Assertions
- **DB (after step 3)**: An outbox row exists for event type `investments.SIPDetected` with `transaction_id` and `sip_registration_id` in the payload.
- **DB (after step 4)**: A `notifications` row exists for this user with `type = 'SIPDetected'`, `read_at = NULL`, and `metadata` containing `transaction_id`, `sip_registration_id`, `instrument_name`, `amount`.
- **API response (step 5)**: HTTP 200; response contains transaction details (date, amount, account, payee/description) and matched SIP details (instrument name, registered amount, debit day, frequency).
- **DB (after step 7)**: An outbox row exists for `investments.SIPLinked` with `transaction_id` and `sip_registration_id`. The `notifications` row has `read_at` set to a non-null timestamp.
- **Events**: `SIPDetected` published; `SIPLinked` published on confirm.
- **Side effects**: The transaction may have its category updated to `"Investments (outflow)"` — note the category name inconsistency; see Known Inconsistencies §1.3.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Transaction deleted before user responds to notification | Confirmation screen returns "This match is no longer valid"; confirm/dismiss buttons hidden; notification is marked read | [ ] |
| SIP registration deactivated (account removed) before user responds | Screen returns "This SIP registration is no longer active"; confirm is disabled; user can only dismiss | [ ] |
| User dismisses the match | No `SIPLinked` event published; `notifications.read_at` set; transaction remains unlinked; SIP registration remains `is_active = true` | [ ] |
| Idempotency: confirm submitted twice (network retry) | Second call is a no-op; no duplicate `SIPLinked` event; HTTP 200 returned | [ ] |
| Same transaction matches two active SIP registrations | Two `SIPDetected` events published; two `notifications` rows created; user must act on each independently; confirming one does not auto-dismiss the other | [ ] |
| User never responds | Notification stays unread indefinitely; no auto-expiry | [ ] |

---

### Scenario 5: Investment Valuation Workflow — Holding to Updated Portfolio View

**Source slice**: `docs/slices/27-add-investment-holding.md` (Step 5), `docs/slices/31-view-portfolio.md`
**Business intent**: After a holding is created with null valuation, the scheduled `MarketPriceFetchWorkflow` (market-traded) or `CalculatedValuationWorkflow` (non-market) fetches/computes a price, updates the holding, upserts a snapshot, and publishes `ValuationUpdated`; the portfolio view subsequently shows the current value.
**Domains involved**: investments, fx (for non-INR instruments)

#### Preconditions
- A `holdings` row exists with `current_value = NULL`, `current_price = NULL`, `last_valued_at = NULL`.
- For `MarketPriceFetchWorkflow`: the instrument has `type IN ('stock', 'mf', 'etf', 'crypto', 'gold', 'us_stock', 'sgb')` and a configured `data_source`.
- For `CalculatedValuationWorkflow`: the instrument has `type IN ('fd', 'ppf', 'bond', 'nps', 'rd')` and (for FDs) a linked `fd_details` row.

#### Steps
1. `GET /api/v1/investments/holdings` — verify the holding appears with `current_value = null` and a "Valuation pending" indicator.
2. Trigger the relevant Temporal workflow run (via test harness or by waiting for the scheduled execution in a staging environment).
3. Confirm the workflow completes successfully.
4. Query `holdings` for the updated values.
5. Query `valuation_snapshots` for today's snapshot.
6. Check the outbox for the `ValuationUpdated` event.
7. `GET /api/v1/investments/holdings` and `GET /api/v1/investments/summary` to confirm the updated value is visible.

#### Assertions
- **DB (after step 4)**: `holdings.current_price` is non-null; `holdings.current_value = units × current_price`; `holdings.last_valued_at` is within the last workflow run window.
- **DB (after step 5)**: A `valuation_snapshots` row exists with `holding_id`, `snapshot_date = today`, `price = holdings.current_price`, `value = holdings.current_value`. Upsert semantics: a second workflow run on the same day overwrites the row, not inserts a duplicate.
- **API response (step 7)**: Portfolio endpoint returns `current_value` as a non-null number; the "Valuation pending" indicator is absent; `last_valued_at` is populated.
- **Events**: An outbox row for `investments.ValuationUpdated` exists with `user_id`, `updated_holding_ids` containing this `holding_id`, and `total_portfolio_value`.
- **Side effects**: For non-INR instruments, `fx.convert()` is used when computing the portfolio total; if the FX rate is stale (> threshold), the portfolio view surfaces a stale-rate warning.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| External price API unavailable for one data source (e.g. Eodhd rate-limited) | Workflow retries up to 3 times with exponential backoff; if still failing, affected holdings are marked stale; other data sources continue; no full workflow failure | [ ] |
| Instrument has no `data_source` configured (user-created instrument) | Holding is skipped silently; `last_valued_at` remains unchanged | [ ] |
| Market closed / weekend | `MarketPriceFetchWorkflow` uses `previousClose` price; `last_valued_at` is updated; portfolio shows "Rate as of {timestamp}" indicator | [ ] |
| `last_valued_at` > 24 hours ago for a market-priced instrument | Portfolio holding card displays "Rate as of {timestamp}" staleness warning | [ ] |
| FD has matured (`maturity_date < today`) | `CalculatedValuationWorkflow` caps `current_value` at `maturity_amount`; a maturity notification is logged/sent — "Your FD matured on {date}" | [ ] |
| Concurrent edit + valuation workflow run | Workflow only writes `current_value`, `current_price`, `last_valued_at`, `valuation_snapshots`; user edits to `units`, `avg_cost_per_unit`, `total_invested` are not overwritten; next workflow run picks up the updated `units` | [ ] |

---

### Scenario 6: View Portfolio — Aggregated View Query

**Source slice**: `docs/slices/31-view-portfolio.md`
**Business intent**: Opening the Investments tab shows the user a complete portfolio overview grouped by instrument type, with current values, gain/loss, and currency-converted totals.
**Domains involved**: investments, fx

#### Preconditions
- User is authenticated.
- At least two holdings exist with populated `current_value` (valuation workflow has run at least once): one INR-denominated (e.g. `stock`) and one non-INR (e.g. `us_stock` priced in USD).
- A current `fx_rates` row exists for USD → INR.

#### Steps
1. `GET /api/v1/investments/summary` (authenticated) — returns PortfolioSummary (total value, invested, PnL). For the full holdings list use `GET /api/v1/investments/holdings`.
2. Inspect the grouped response sections.
3. Verify the portfolio total calculation.
4. Tap (or request) an individual holding detail.

#### Assertions
- **API response**: HTTP 200; response contains:
  - `total_portfolio_value_inr`: equals `SUM(fx_convert(current_value, instrument.currency, 'INR'))` across all holdings.
  - Holdings grouped by type (stocks, mutual funds, ETFs, fixed deposits, PPF/NPS, crypto, gold/SGB, US stocks, other).
  - Each holding shows: `name`, `units`, `current_value`, `total_invested`, `gain_loss_amount = current_value - total_invested`, `gain_loss_pct`, `last_valued_at`.
  - The holding with `last_valued_at` > 24 hours ago (market-priced) includes a staleness indicator.
- **DB**: The `current_value` values shown match the `holdings` table (no re-computation at query time; the portfolio view reads stored values).
- **Events**: None triggered by a read.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| No holdings exist for the user | `GET /api/v1/investments/summary` returns HTTP 200 with `total_value = 0`, `total_invested = 0`, `pnl = 0`; `GET /api/v1/investments/holdings` returns an empty list | [ ] |
| Holding has `current_value = NULL` (valuation not yet run) | Holding appears in the list with `current_value = null` and a "Updating..." / "Valuation pending" state; excluded from `total_portfolio_value_inr` sum | [ ] |
| Instrument delisted / data source permanently unavailable | `last_valued_at` falls behind; staleness warning shown; portfolio continues to display last known value | [ ] |

---

### Scenario 7: View Portfolio Historical Value Chart

**Source slice**: `docs/slices/32-view-portfolio-history.md`
**Business intent**: The user can select a time range and see a time-series chart of total portfolio value, plus drill into individual holding history.
**Domains involved**: investments, fx

#### Preconditions
- At least two `valuation_snapshots` rows exist for this user's holdings on different dates within the chosen time range.
- At least one holding has a non-INR currency so that historical FX conversion is exercised.

#### Steps
1. `GET /api/v1/investments/history?from_date=2026-04-17&to_date=2026-05-17` (1-month range).
2. Verify the aggregated daily series.
3. `GET /api/v1/investments/history` with the full available date range.
4. Query individual holding history — confirm whether a per-holding history endpoint exists; if not, filter from `GET /api/v1/investments/history` by `holding_id` if supported.
5. Tap a specific data point on the chart (or `GET /api/v1/investments/history?from_date=2026-04-01&to_date=2026-04-01`) to fetch composition on that date.

#### Assertions
- **API response (step 2)**: HTTP 200; response contains an array of `{ date, total_value_inr }` objects for each day in the 1-month range. Each `total_value_inr` equals `SUM(valuation_snapshots.value converted to INR using fx_rates for that date)` for all holdings with a snapshot on that day.
- **API response (step 4)**: Individual holding history returns `{ date, value, price }` pairs in the holding's native currency (not converted to INR).
- **API response (step 5)**: Returns `total_value_inr` and a breakdown by holding (name, value, currency) for the queried date.
- **DB**: The values returned match raw `valuation_snapshots` rows joined with historical `fx_rates` using `as_of_date`; no re-computation beyond the formula is performed at query time.
- **Events**: None.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Gap in snapshot history (workflow did not run on a specific day) | The chart shows no data point for that day (gap is visible); the previous known value is not interpolated by the API — interpolation is a UI-layer concern | [ ] |
| Holding added recently; queried range extends before holding's creation date | History only starts from the holding's first `valuation_snapshots` row; earlier dates show no data for that holding | [ ] |
| Historical FX rate not available for a specific date | `fx.convert()` falls back to the closest available rate; the rate-used date is included in the response footnote | [ ] |

---

### Scenario 8: Edit Investment Holding

**Source slice**: `docs/slices/41-edit-investment-holding.md`
**Business intent**: A user corrects or updates a holding's units, average cost, or total invested after the initial creation; FD holdings also allow editing of FD-specific terms.
**Domains involved**: investments

#### Preconditions
- User is authenticated.
- A `holdings` row exists and belongs to this user.
- For the FD sub-case: a linked `fd_details` row exists.

#### Steps
1. `GET /api/v1/investments/holdings` to confirm pre-edit values (filter for the target `holding_id`).
2. `PATCH /api/v1/investments/holdings/{holding_id}` with body:
   ```json
   {
     "units": 15,
     "avg_cost_per_unit": 1480.00,
     "total_invested": 22200.00,
     "as_of_date": "2026-05-17"
   }
   ```
3. Verify the API response.
4. Query the `holdings` table directly.
5. `GET /api/v1/investments/holdings` and `GET /api/v1/investments/summary` to confirm the updated values appear.

#### Assertions
- **DB**: `holdings.units = 15`, `holdings.avg_cost_per_unit = 1480.00`, `holdings.total_invested = 22200.00`, `holdings.updated_at` refreshed. `holdings.current_value` and `holdings.current_price` are **unchanged** from before the edit (valuation is not recalculated at save time).
- **API response**: HTTP 200; response body reflects the updated `units`, `avg_cost_per_unit`, `total_invested`; `current_value` shown is the pre-edit value; a "Value as of {last_valued_at}" staleness note is present.
- **Events**: No events published by this edit operation. `ValuationUpdated` will be published only on the next workflow run.
- **Side effects**: For FD holdings, if `fd_details` fields were also updated (principal, rate, tenure, start_date, compounding), `maturity_date` and `maturity_amount` on the `fd_details` row are recomputed in the same transaction.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `units` edited to 0 | HTTP 200 — zero-unit holding is stored (not deleted); portfolio view may filter it from the active list but the row persists for historical reference | [ ] |
| `instrument_id` included in the PATCH body | HTTP 422 or ignored — instrument cannot be changed after initial creation; the response should indicate this field is read-only | [ ] |
| `avg_cost_per_unit` updated without updating `total_invested` | HTTP 200 — both fields are stored independently; no validation error; UI may show a note that `avg_cost_per_unit × units ≠ total_invested` | [ ] |
| FD `start_date` updated such that `maturity_date < today` | HTTP 200 — recomputed `maturity_date` is in the past; `CalculatedValuationWorkflow` will cap the value at `maturity_amount` on next run | [ ] |
| Edit submitted while `MarketPriceFetchWorkflow` is mid-run | No data corruption; workflow writes only `current_value`, `current_price`, `last_valued_at`, `valuation_snapshots`; `units` and cost fields written by the edit are not overwritten | [ ] |

---

### Scenario 9: Duplicate Holding — 409 Conflict Path

**Source slice**: `docs/slices/27-add-investment-holding.md` (Edge Cases)
**Business intent**: Each instrument can appear at most once in a user's portfolio; attempting to add a second holding for the same instrument returns a 409 Conflict.
**Domains involved**: investments

#### Preconditions
- User is authenticated.
- A `holdings` row already exists for `user_id = <user>` and `instrument_id = <instr>`.

#### Steps
1. `POST /api/v1/investments/holdings` with the same `instrument_id` that already has a holding for this user.
2. Verify the response.
3. Query the `holdings` table to confirm only one row exists.

#### Assertions
- **DB**: Exactly one `holdings` row exists for this `user_id` + `instrument_id`; no second row was inserted.
- **API response**: HTTP 409; error body contains message "You already hold this instrument. Edit the existing holding instead." and ideally a reference to the existing `holding_id`.
- **Events**: None.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Idempotency key re-sent (genuine retry after network failure on the original insert) | HTTP 201 returned with the already-created holding (not a 409); idempotency key is honoured | [ ] |

---

## Known Inconsistencies

### [1.3] "Investment — SIP" category name not in seeded defaults

- **Source**: `docs/business-intent/INCONSISTENCIES.md` §1.3
- **Conflict**: `slices/30-confirm-sip-detection.md` (Step 3a) states the transaction's category may be updated to `"Investment — SIP"` on confirmation. `domains/categorization.md` lists `"Investments (outflow)"` as the seeded default category; there is no `"Investment — SIP"` category in the seed data.
- **Impact**: If the confirm handler references a category name that does not exist, the category update will fail silently or throw an error. Tests for Scenario 4 (confirm step) should assert that the assigned category is `"Investments (outflow)"` — or a TODO to resolve which name is correct must be tracked before the confirm handler is implemented.
- **TODO**: Resolve whether `"Investment — SIP"` is an undocumented sub-category, or whether Step 3a should reference `"Investments (outflow)"`.

### [1.5] SIP deactivation notification missing from notifications domain

- **Source**: `docs/business-intent/INCONSISTENCIES.md` §1.5
- **Conflict**: `slices/29-register-sip.md` (edge case: "Bank account removed after registration") states "A future `SIPRegistrationDeactivated` event could notify the user." However, the `domains/investments.md` clarifies that deactivation is **silent** — no in-app notification is sent. `domains/notifications.md` has no handler for any SIP-deactivation event.
- **Impact**: Scenario 3 edge case "AccountRemoved deactivates SIP" must assert that `is_active = false` is set **and** that no notification is created. Any test expecting a deactivation notification will fail and is incorrect per the current domain implementation.
- **TODO**: Either add a `SIPRegistrationDeactivated` event to the investments domain and a corresponding handler in the notifications domain, or confirm the silent deactivation is the intended product behaviour and remove the promise from slice 29.

### [3.12] One holding per instrument per user (409 Conflict on duplicate)

- **Source**: `docs/business-intent/INCONSISTENCIES.md` §3.12
- **Conflict**: `business-intent/investments.md` does not document the unique constraint on `(user_id, instrument_id)` in `holdings`. The constraint is described only in `slices/27-add-investment-holding.md` (edge cases).
- **Impact**: The 409 Conflict path is a real, enforced behaviour (Scenario 9). Tests that attempt to add a second holding for the same instrument without awareness of this constraint will fail. All test setups that use the same fixture instrument for multiple test runs must either clean up the holding row between runs or use distinct instruments per scenario.
- **TODO**: Add an explicit note to `business-intent/investments.md` that each instrument can appear at most once per user.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| `CalculatedValuationWorkflow` — PPF, RD, bond, NPS formula assertions | `docs/workflows/investment-valuation.md` | Write dedicated unit/integration tests for each formula type; the E2E scenarios above cover FD only. |
| `MarketPriceFetchWorkflow` — per-data-source contract tests (AMFI, Eodhd, CoinGecko, Twelve Data, metals-api) | `docs/workflows/investment-valuation.md` | Each data source should have a test with a mocked HTTP response asserting correct price parsing and `holdings` update. |
| FD maturity notification ("Your FD matured — did you renew or redeem it?") | `docs/workflows/investment-valuation.md` step 4 | Add a scenario covering the notification published when `maturity_date < today` during `CalculatedValuationWorkflow`. |
| Portfolio history — FX fallback when historical rate is missing | `docs/slices/32-view-portfolio-history.md` | Scenario 7 edge case is listed but the fallback behaviour of `fx.convert()` with `as_of_date` needs an explicit integration test against the fx domain. |
| Instrument search / suggestion endpoint | `docs/slices/27-add-investment-holding.md` Steps 2–3 | No test scenario covers the instrument search (partial-match query on `instruments` by `ticker` or `name`); add a scenario for the search step. |
| `SIPLinked` double-confirm deduplication | `docs/slices/30-confirm-sip-detection.md` | Edge case listed in Scenario 4 but requires a concurrent-request test; flagged for explicit test implementation. |
| Delete holding — endpoint exists but no test scenario covers it | `docs/business-intent/INCONSISTENCIES.md` §4 (missing slices) | The `DELETE /api/v1/investments/holdings/{holding_id}` endpoint exists and returns 204. A test scenario should be written for this. See TODO. |
| SIP re-activation after account is restored | `docs/business-intent/INCONSISTENCIES.md` §3.5 | Slice 08 states SIPs are NOT auto-reactivated on account restore; an explicit test asserting `is_active` stays `false` after account reactivation should be added. |

---

## TODO

- [ ] Resolve category name inconsistency [1.3]: confirm whether `"Investment — SIP"` or `"Investments (outflow)"` should be assigned on SIP confirmation (Scenario 4).
- [ ] Resolve SIP deactivation notification gap [1.5]: decide and document whether a `SIPRegistrationDeactivated` event and notification are in scope.
- [ ] Add explicit unique-constraint documentation to `business-intent/investments.md` for the one-holding-per-instrument rule [3.12].
- [ ] Write a scenario for `DELETE /api/v1/investments/holdings/{holding_id}` — endpoint exists and returns 204 but no test scenario covers it. The scenario should verify: (a) the holding row is deleted, (b) associated `fd_details` and `valuation_snapshots` rows are cascade-deleted or cleaned up, and (c) `GET /api/v1/investments/holdings` no longer returns the deleted holding. Also confirm whether a slice exists; if not, write the slice first.
- [ ] Write per-data-source contract tests for `MarketPriceFetchWorkflow` (AMFI, Eodhd, CoinGecko, Twelve Data, metals-api).
- [ ] Write formula coverage tests for `CalculatedValuationWorkflow` (PPF, RD, bond, NPS types beyond FD).
- [ ] Add FD maturity notification test scenario once the notification event is confirmed to be published.
- [ ] Add instrument search endpoint test scenario.
- [ ] Determine and document the SIP re-activation policy after account restore; add a corresponding assertion in the SIP edge case tests.
