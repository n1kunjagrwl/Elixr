# fx — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The fx domain is invisible to users but essential to the app's coherence: it fetches exchange rates from exchangerate-api.com every 6 hours, stores them in PostgreSQL, and provides a single `convert()` service method that every other domain calls when it needs to express a foreign currency amount in INR. Without it, Indian users who hold NRE/NRO accounts, US stocks, or crypto holdings would see either hardcoded rates, per-domain API calls, or missing INR totals across their portfolio, budget, and transaction views. The fx domain solves this by being the one place the whole app agrees on what 1 USD or 1 EUR is worth in INR today.

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `fx_rates` — one row per `(from_currency, to_currency)` pair, upserted on each refresh |
| Events published | None — the fx domain has no outbox table and publishes no domain events |
| Events consumed | None — the fx domain subscribes to no events from other domains |
| Temporal workflows | `FXRateRefreshWorkflow` — scheduled every 6 hours (00:00, 06:00, 12:00, 18:00 IST); fetches rates from exchangerate-api.com and upserts into `fx_rates` |
| Slices covered | (none — indirect participant) |

## Test Scenarios

---

### Scenario 1: FXRateRefreshWorkflow — Scheduled Happy Path

**Source**: `docs/workflows/fx-rate-refresh.md`
**Business intent**: The scheduled workflow runs at a fixed 6-hour cadence, fetches current rates from exchangerate-api.com, and upserts them into `fx_rates` so all domains get a rate no more than 6 hours stale.
**Domains involved**: fx

#### Preconditions
- Temporal scheduler is running and `FXRateRefreshWorkflow` is registered with cron expression for 00:00, 06:00, 12:00, 18:00 IST.
- exchangerate-api.com is reachable (or stubbed to return a valid `/v6/{key}/latest/INR` response).
- At least one `bank_accounts` or `instruments` row with `currency != 'INR'` exists to exercise the dynamic currency discovery query; the fixed baseline set (USD, EUR, GBP, SGD, AED, JPY, CHF, CAD, AUD, HKD) is always included regardless.

#### Steps
1. Allow the Temporal schedule to fire (or trigger the workflow manually in a test environment).
2. Activity `fetch_fx_rates` calls `GET /v6/{key}/latest/INR` — stub returns `{"base": "INR", "rates": {"USD": 0.01194, "EUR": 0.01098, "GBP": 0.00952, ...}}`.
3. Workflow inverts rates (`1 INR = 0.01194 USD` → `1 USD = 83.75 INR`) and upserts all pairs.
4. Workflow also stores inverse rates (INR→USD, INR→EUR, etc.) in the same upsert pass.
5. Workflow exits successfully.

#### Assertions
- **DB**: `fx_rates` contains a row for each currency in the fixed baseline set with `to_currency = 'INR'` — `from_currency IN ('USD', 'EUR', 'GBP', 'SGD', 'AED', 'JPY', 'CHF', 'CAD', 'AUD', 'HKD')`.
- **DB**: Corresponding inverse rows exist — `from_currency = 'INR'`, `to_currency IN (same set)`.
- **DB**: `fetched_at` for all upserted rows is within the last 60 seconds of the workflow completion time.
- **DB**: `rate` for `(USD, INR)` equals `1 / 0.01194 ≈ 83.75` (within floating-point tolerance of 4 decimal places).
- **DB**: Unique constraint `(from_currency, to_currency)` means exactly one row per pair — no duplicate rows inserted.
- **API response**: Not applicable — this workflow exposes no HTTP endpoint.
- **Events**: None — the fx domain publishes no outbox events.
- **Side effects**: Temporal marks the workflow execution as `COMPLETED`. Subsequent calls to `fx.convert()` use the newly upserted rates.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| No user data exists (no non-INR accounts or instruments) | Workflow still fetches and stores the 10 fixed baseline currencies | [ ] |
| A user has a non-INR account currency not in the fixed baseline (e.g., `CHF` is baseline, but user has `THB`) | `THB` is added to the fetch list; `fx_rates` gains a `(THB, INR)` row | [ ] |
| Rate value in API response is `0` or negative | Workflow should reject / log an error for that specific pair; other pairs are still stored; TODO: exact behaviour not documented — see Coverage Gaps | [ ] |
| Workflow fires while a prior execution is still running (duplicate schedule trigger) | Temporal prevents concurrent runs via workflow ID — second trigger is queued or dropped; no duplicate upsert race | [ ] |

---

### Scenario 2: FXRateRefreshWorkflow — API Unavailable (Stale Rate Handling)

**Source**: `docs/workflows/fx-rate-refresh.md`, `docs/integrations.md`
**Business intent**: When exchangerate-api.com is unreachable, the system degrades gracefully — existing cached rates remain intact and are still used for conversions, avoiding a total breakdown of multi-currency display.
**Domains involved**: fx

#### Preconditions
- `fx_rates` contains existing rows with `fetched_at = now() - 4 hours` (recent enough to be within normal TTL).
- exchangerate-api.com is stubbed to return HTTP 503 or a connection timeout on all attempts.

#### Steps
1. Temporal schedule fires `FXRateRefreshWorkflow`.
2. Activity `fetch_fx_rates` fails — stubbed API returns 503.
3. Temporal retries the activity per policy: up to 5 attempts, initial interval 30s, backoff coefficient 2.0, max interval 10 minutes.
4. All 5 attempts fail.
5. Workflow exits with failure status.

#### Assertions
- **DB**: Pre-existing `fx_rates` rows are **not modified or deleted** — `rate` and `fetched_at` values from the prior successful run remain unchanged.
- **DB**: No new rows inserted; no rows removed.
- **API response**: Not applicable.
- **Events**: None.
- **Side effects**: Temporal marks the workflow execution as `FAILED`. The application health check endpoint returns a `warning` (not an error) if `fx_rates.fetched_at` for any active currency is older than 12 hours. Calls to `fx.convert()` still succeed using the last known rate.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `fx_rates` is empty (first-ever run fails) | `fx.convert()` raises `FXRateUnavailableError`; callers receive no INR equivalent; UI must handle this gracefully (TODO: exact UI fallback not documented) | [ ] |
| Stale rate is 20 hours old (within 24-hour warning threshold) | `fx.convert()` proceeds without a warning; no user-visible alert | [ ] |
| Stale rate is 25 hours old (exceeds 24-hour threshold) | `fx.convert()` logs a warning with the `last_available_rate.fetched_at`; portfolio view should display "rate as of {fetched_at}" to the user | [ ] |
| API returns a partial response (some currencies missing) | Only the returned currencies are upserted; missing currencies retain their prior rate and `fetched_at`; no rows are deleted for missing currencies | [ ] |
| Temporal server itself is down during a scheduled run time | Temporal fires the missed run when the server comes back online (Temporal catch-up behaviour); no manual intervention required | [ ] |

---

### Scenario 3: `fx.convert()` — Direct INR Conversion

**Source**: `docs/domains/fx.md`
**Business intent**: Any domain (investments, transactions, budgets, earnings) can convert a foreign currency amount to INR with a single service call that reads from the cache — no live API call at request time.
**Domains involved**: fx (called by investments, transactions, budgets, earnings)

#### Preconditions
- `fx_rates` contains a row: `(from_currency='USD', to_currency='INR', rate=83.75, fetched_at=<recent>)`.

#### Steps
1. Domain code calls `fx.convert(amount=Decimal("100"), from_currency="USD", to_currency="INR")`.
2. Service performs a DB lookup for `(USD, INR)`.
3. Returns `Decimal("8375.00")`.

#### Assertions
- **DB**: No write occurs — `convert()` is a read-only operation.
- **API response**: The calling domain's API endpoint returns the INR-converted value as part of its own response (e.g., portfolio total, transaction INR equivalent). The exact field depends on the calling domain.
- **Events**: None.
- **Side effects**: No external API call is made. The result is derived entirely from `fx_rates`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| `from_currency == to_currency` (e.g., INR→INR) | Returns `amount` unchanged, no DB lookup required | [ ] |
| `from_currency == 'INR'` | Reads the `(INR, to_currency)` inverse rate row and multiplies | [ ] |
| `to_currency == 'INR'` (standard case) | Reads the `(from_currency, INR)` row and multiplies | [ ] |
| Rate row exists but `fetched_at` is 25+ hours ago | Service logs a warning; returns the stale rate; does not raise an error | [ ] |
| No rate row found for the requested pair | Raises `FXRateUnavailableError` with the currency pair and the `last_available_rate.fetched_at` timestamp | [ ] |

---

### Scenario 4: `fx.convert()` — Non-INR to Non-INR Triangulation

**Source**: `docs/domains/fx.md`, `docs/workflows/fx-rate-refresh.md`
**Business intent**: When a user's data requires converting between two non-INR currencies (e.g., USD holdings priced in EUR), the domain triangulates through INR rather than storing N² rate pairs, keeping the rate table simple.
**Domains involved**: fx

#### Preconditions
- `fx_rates` contains:
  - `(from_currency='USD', to_currency='INR', rate=83.75)`
  - `(from_currency='INR', to_currency='EUR', rate=0.01098)` — i.e., the inverse EUR→INR row was stored as `(from_currency='EUR', to_currency='INR', rate=91.07)` and its inverse.

#### Steps
1. Domain code calls `fx.convert(amount=Decimal("100"), from_currency="USD", to_currency="EUR")`.
2. Service looks up `(USD, INR)` rate = 83.75 and `(INR, EUR)` rate = 0.01098.
3. Returns `Decimal("100") * Decimal("83.75") * Decimal("0.01098") ≈ Decimal("91.96")`.

#### Assertions
- **DB**: No write occurs.
- **API response**: Calling domain's response reflects the triangulated value.
- **Events**: None.
- **Side effects**: Two DB reads (not one) for a non-INR pair; calling code should be aware of this for performance-sensitive paths.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| One leg of the triangulation is missing (e.g., USD→INR exists but INR→EUR does not) | Raises `FXRateUnavailableError` indicating the missing pair | [ ] |
| Both source and target currency are the same non-INR currency (e.g., USD→USD) | Returns `amount` unchanged before any DB lookup | [ ] |

---

### Scenario 5: Non-INR Transaction Displayed with INR Equivalent

**Source**: `docs/business-intent/fx.md`, `docs/domains/fx.md`
**Business intent**: A transaction made on a foreign-currency credit card is imported into the system; the transactions/statements domain calls `fx.convert()` so the user sees both the original foreign amount and its INR equivalent in the transaction list.
**Domains involved**: fx, transactions (or statements)

#### Preconditions
- A transaction row exists with `currency = 'USD'` and `amount = 50.00` (representing a $50 foreign purchase).
- `fx_rates` contains `(from_currency='USD', to_currency='INR', rate=83.75, fetched_at=<recent>)`.

#### Steps
1. Calling domain (transactions or statements) invokes `fx.convert(amount=Decimal("50"), from_currency="USD", to_currency="INR")`.
2. Service returns `Decimal("4187.50")`.
3. API endpoint for the transaction list (in the transactions domain) returns the transaction with both original amount and INR equivalent.

#### Assertions
- **DB**: `fx_rates` row for `(USD, INR)` is not modified — this is a read-only path.
- **API response**: Transaction entry contains the original amount in USD **and** the INR equivalent `4187.50`.
- **Events**: None from the fx domain.
- **Side effects**: The INR equivalent shown is based on the current cached rate, not the rate at the time of the transaction — this is expected behaviour for personal finance display (not an accounting system).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Transaction currency is INR (standard case) | `fx.convert()` returns the amount unchanged; no FX lookup performed | [ ] |
| Transaction currency is USD but no USD→INR rate in cache | Calling domain receives `FXRateUnavailableError`; UI displays original currency without INR equivalent, or shows an error indicator | [ ] |
| User requests the historical rate at transaction date via `as_of_date` parameter | `convert()` selects the `fx_rates` row with `fetched_at` closest to the given date; if no historical row exists, raises `FXRateUnavailableError` | [ ] |
| Rate is more than 24 hours old | Service logs a warning; UI should render "rate as of {fetched_at}" label next to the INR equivalent | [ ] |

---

### Scenario 6: Investment Portfolio Valuation in INR (US Stock Example)

**Source**: `docs/business-intent/fx.md`, `docs/integrations.md` (Twelve Data section)
**Business intent**: A user's US stock holding (priced in USD by Twelve Data) is converted to INR by the investments domain calling `fx.convert()` so the portfolio screen shows a consistent INR total across Indian and foreign holdings.
**Domains involved**: fx, investments

#### Preconditions
- A `holdings` row exists for a US stock instrument with a current price in USD (e.g., 10 shares × $150.00 = $1,500.00).
- `fx_rates` contains `(from_currency='USD', to_currency='INR', rate=83.75, fetched_at=<recent>)`.

#### Steps
1. `MarketPriceFetchWorkflow` (investments domain) fetches the USD price from Twelve Data.
2. Investments domain calls `fx.convert(amount=Decimal("1500.00"), from_currency="USD", to_currency="INR")`.
3. Service returns `Decimal("125625.00")`.
4. Portfolio total includes this INR value alongside INR-denominated holdings.

#### Assertions
- **DB**: `fx_rates` row is not modified — read-only.
- **API response**: Portfolio endpoint returns the US stock valued at `125625.00 INR`; portfolio total aggregates INR and converted foreign values correctly.
- **Events**: None from the fx domain.
- **Side effects**: The `fetched_at` timestamp from `fx_rates` may be surfaced in the UI as "FX rate as of {fetched_at}" for transparency.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| FX rate is stale (>24 hours) but market price is fresh | Portfolio value is computed with the stale rate; UI shows staleness warning on the FX rate, not on the market price | [ ] |
| Both FX rate and market price are unavailable | Portfolio shows last known values with timestamps; does not show zero or crash | [ ] |
| Instrument currency is INR (e.g., NSE stock) | `fx.convert()` with `from_currency == to_currency` returns price unchanged; no FX row is consulted | [ ] |

---

### Scenario 7: Budget Spend Includes Foreign Currency Transaction

**Source**: `docs/business-intent/fx.md`
**Business intent**: When a user spends on a forex credit card and the transaction is categorised into a budget category, the budgets domain converts the foreign amount to INR via `fx.convert()` before updating `budget_progress.current_spend`, ensuring the budget total is always in INR.
**Domains involved**: fx, budgets, transactions

#### Preconditions
- A budget exists for category "Travel" with `limit_amount = 20000 INR` and `current_spend = 0`.
- A USD-denominated transaction of $100 is categorised as "Travel".
- `fx_rates` contains `(from_currency='USD', to_currency='INR', rate=83.75)`.

#### Steps
1. Transaction is categorised (via statements import or manual entry) as "Travel", `currency = 'USD'`, `amount = 100.00`.
2. Budgets domain handler calls `fx.convert(100, "USD", "INR")` → `8375.00`.
3. `budget_progress.current_spend` is incremented by `8375.00`.

#### Assertions
- **DB**: `budget_progress.current_spend = 8375.00` after the transaction is processed.
- **DB**: `fx_rates` row is unchanged (read-only path).
- **API response**: Budget progress endpoint shows `current_spend = 8375.00` and `percentage = 41.875%` against a `20000 INR` limit.
- **Events**: None from the fx domain.
- **Side effects**: If `current_spend` after conversion exceeds 80% of `limit_amount`, the budgets domain fires its alert event as normal — the threshold logic is unaffected by currency conversion.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| FX rate unavailable when transaction is categorised | Budgets domain receives `FXRateUnavailableError`; TODO: exact handling not documented — does the budget update fail silently, retry, or use a fallback? | [ ] |
| Same transaction re-categorised after the FX rate has changed | Budget `current_spend` is adjusted using the rate at re-categorisation time, not the original transaction time — this is a known limitation (no `as_of_date` used here) | [ ] |

---

## Known Inconsistencies

No entries in `docs/business-intent/INCONSISTENCIES.md` directly reference the fx domain. However, two entries have indirect fx relevance:

- **[3.10] Multi-currency settlement limitation**: `slices/35-record-peer-settlement.md` describes settling a USD-denominated peer balance with an INR payment — `remaining_amount` is not automatically reduced because the balance and settlement are in different currencies. The fx domain's `convert()` is not called in this path to normalise the currencies; the limitation is in the peers domain's ledger design. The fx domain itself is not at fault, but a future fix would involve calling `fx.convert()` at settlement time. This should be noted when writing peer-settlement tests.

- **[1.5] SIP registration deactivation notification**: Not fx-related, included here for completeness — no fx impact.

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| No dedicated slice for FX rate display (how the UI surfaces "rate as of {date}" to users) | `docs/business-intent/fx.md` — user interaction table describes this label | [ ] write slice `fx-rate-display.md` covering portfolio, transaction list, and budget contexts |
| `as_of_date` parameter behaviour is documented in `fx.md` but no scenario covers a caller explicitly requesting a historical rate (e.g., displaying a transaction in the month it occurred) | `docs/domains/fx.md` — `convert()` signature | [ ] add Scenario 8 for historical `as_of_date` lookup once the DB retention policy for old `fx_rates` rows is clarified |
| Behaviour when `fx_rates` is completely empty (e.g., first deploy before the first workflow run) | `docs/workflows/fx-rate-refresh.md` — notes retry policy but not the cold-start state | [ ] document cold-start handling: does the app block requests or return errors until the first successful refresh? |
| The 24-hour staleness warning is logged server-side — it is unclear whether the UI reads a field from the API response to decide whether to show the "rate as of {date}" label, or infers it from `fetched_at` | `docs/domains/fx.md` — "UI can display 'rate as of {fetched_at}'" | [ ] confirm API contract: does the API response include `rate_fetched_at` on relevant endpoints? |
| Health check endpoint behaviour (warning when `fetched_at` > 12 hours) is mentioned in `fx-rate-refresh.md` but the health check endpoint path and response schema are not documented | `docs/workflows/fx-rate-refresh.md` — "application health check endpoint should return a warning" | [ ] document health check endpoint contract and add a test for the stale-rate warning response |
| Rate for a non-standard pair (e.g., `SGD→AED`) involving two non-INR currencies — triangulation logic is documented but not tested end-to-end | `docs/domains/fx.md` — triangulation section | [ ] extend Scenario 4 with a SGD→AED case once inverse rate storage is confirmed |
| Zero or invalid rate values from the API (e.g., API returns `"USD": 0`) are not handled in the workflow doc | `docs/workflows/fx-rate-refresh.md` — no validation step described | [ ] add input validation step to workflow doc and corresponding edge case |

## TODO

- [ ] Confirm that `FXRateRefreshWorkflow` actually queries `bank_accounts`, `credit_cards`, and `instruments` inside a Temporal **activity** (not the workflow itself) to preserve determinism — **Blocker**: If the DB query runs in workflow code, it violates the Temporal determinism constraint — **Next step**: Read `src/elixir/domains/fx/workflows/` once implemented to verify.
- [ ] Clarify DB retention policy for `fx_rates` — the unique constraint means only one row per pair is kept (upserted); the `as_of_date` parameter in `convert()` implies historical rows, but the upsert pattern overwrites history — **Blocker**: Scenario for historical rate lookup (as_of_date) cannot be written until retention is resolved — **Next step**: Ask domain owner whether historical rows are ever kept, or whether `as_of_date` is effectively a no-op in the current design.
- [ ] Determine the exact error contract for `FXRateUnavailableError` — which HTTP status code does each calling domain surface to the client when this is raised? (Scenarios 5, 6, 7 edge cases) — **Blocker**: API response assertions in edge cases are incomplete — **Next step**: Check `src/elixir/domains/fx/services.py` and each calling domain's `api.py` error handler.
- [ ] Verify that inverse rate rows (INR→USD, INR→EUR, etc.) are stored correctly and that `convert()` uses them for the `from_currency == 'INR'` branch — the workflow doc describes this in Step 4 but the `convert()` pseudocode in `fx-rate-refresh.md` uses `fetch_rate('INR', to_currency)` which must match a stored `(INR, to_currency)` row — **Next step**: Read `src/elixir/domains/fx/services.py` to confirm.
- [ ] Add Playwright E2E tests for multi-currency display in the portfolio screen and transaction list — these are the primary user-visible surfaces where fx correctness matters — **Blocker**: Endpoint contracts for portfolio and transaction list endpoints must be confirmed first — **Next step**: After confirming API schemas, scaffold tests at `client/tests/portfolio/` and `client/tests/transactions/` that assert INR equivalents appear correctly.
- [ ] Confirm free-tier rate limit sufficiency: 4 runs/day × 1 API call per run = ~120 calls/month against a 1,500/month free limit — currently safe, but if user base grows and the currency list expands significantly, the single-call approach (fetching all currencies in one `latest/INR` request) must be verified as still covered — **Next step**: Confirm the exchangerate-api.com free-tier response includes all needed currencies in a single call.
