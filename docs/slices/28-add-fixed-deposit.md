# Slice: Add Fixed Deposit

## User Goal
Record a fixed deposit with its full parameters so the app tracks its accrued value and maturity date automatically.

## Trigger
User selects "Fixed Deposit" from the investment type picker (from slice 27) or taps "Add FD" directly on the Investments screen.

## Preconditions
- User is authenticated.
- The FD instrument type (`type = 'fd'`) is available in the system.

## Steps

### Step 1: Enter FD Identification
**User action**: User types the name of the FD (e.g. "SBI FD — Savings", "HDFC Bank FD"). This is a free-text label; no ticker lookup is needed.

**System response**: Backend checks whether an `instruments` row with `type = 'fd'` and `name` matching the entered text already exists for any user. If it does, it is reused (shared master table). If not, a new `instruments` row is created with `type = 'fd'`, `currency = 'INR'` (default), and no `ticker`, `isin`, `exchange`, or `data_source` (none apply to FDs). The `govt_rate_percent` field is left null (FDs use a user-specified rate, not a govt rate).

### Step 2: Enter Principal and Rate
**User action**: User fills in:
- **Principal** (₹) — the amount deposited.
- **Rate (% per annum)** — the annual interest rate offered by the bank.

**System response**: UI validates that principal > 0 and 0 < rate ≤ 50 (a sanity upper bound). A live preview line is shown: "At {rate}% per annum…".

### Step 3: Enter Tenure and Start Date
**User action**: User selects:
- **Start date** — the date the FD was opened (defaults to today; may be backdated).
- **Tenure** — expressed as years + months + days in the UI; converted to `tenure_days` internally (using calendar-accurate day counting from `start_date`).

**System response**: UI computes and displays `maturity_date = start_date + tenure_days`. A human-readable label is shown: "Matures on {maturity_date} ({N} days from now / {N} days ago if backdated)".

### Step 4: Select Compounding Frequency
**User action**: User picks one of: Monthly, Quarterly, Annually, Simple Interest.

**System response**: UI updates the maturity amount preview using the formula appropriate to the selection:
- Monthly / Quarterly / Annually: `maturity_amount = principal × (1 + rate/n)^(n × t)` where `n` is compounding periods per year and `t` is tenure in years.
- Simple: `maturity_amount = principal × (1 + rate × t)`.

The preview displays: "Estimated maturity amount: ₹{maturity_amount}" and "Total interest earned: ₹{maturity_amount − principal}".

### Step 5: Submit
**User action**: User reviews the summary and taps "Save FD".

**System response**:
1. Backend inserts or reuses the `instruments` row (type = 'fd').
2. Backend inserts a `holdings` row:
   - `units = 1` (FDs are tracked as a single unit).
   - `avg_cost_per_unit = principal`.
   - `total_invested = principal`.
   - `current_value` and `current_price` set to null initially; will be computed by CalculatedValuationWorkflow.
   - `last_valued_at = null`.
3. Backend inserts an `fd_details` row linked to the new `holding_id`:
   - `principal`, `rate_percent`, `tenure_days`, `start_date`, `maturity_date`, `compounding` stored as entered.
   - `maturity_amount` computed and stored at creation time using the formula from Step 4.
4. The next run of **CalculatedValuationWorkflow** (daily 00:30 IST) computes the current accrued value using `P × (1 + r/n)^(n × t_elapsed)` and writes it to `holdings.current_value` and `holdings.current_price`, and upserts a `valuation_snapshots` row.
5. UI shows the FD card immediately with principal as the "invested" amount and "Valuation pending" badge until the workflow runs.

## Domains Involved
- **Investments**: Core domain. Creates `instruments` and `holdings` rows, writes `fd_details`, triggers daily valuation via CalculatedValuationWorkflow.

## Edge Cases & Failures
- **Maturity date in the past (backdated FD)**: Allowed. The UI shows "This FD has already matured." as an informational banner. CalculatedValuationWorkflow computes value as of maturity (capped at `maturity_amount`) rather than beyond it.
- **Rate = 0**: Rejected with a 422 validation error — an FD with 0% interest is not a valid FD entry. User should use "Other" instrument type instead.
- **Tenure = 0 days**: Rejected with a 422 validation error.
- **Compounding frequency mismatch**: If the user selects "Monthly" but the bank compounds quarterly, the stored `maturity_amount` may differ slightly from the actual amount. The system stores what the user entered; the user is responsible for entering the correct compounding frequency.
- **Same FD entered twice**: No automatic deduplication. The user will see two FD holdings with the same name. They can delete the duplicate manually.
- **Network error during submit**: Frontend retries with idempotency key. If the `holdings` row was already created, the second request returns the existing holding.

## Success Outcome
The FD is visible in the portfolio with its principal, maturity date, compounding frequency, and estimated maturity amount. From the following morning, it shows a daily-updated accrued value reflecting interest earned to date.
