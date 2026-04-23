# Slice: View Investment Portfolio

## User Goal
See the current value, gain/loss, and composition of all investments at a glance.

## Trigger
User navigates to the Investments tab.

## Preconditions
- User is authenticated.
- At least one active `holdings` row exists.

## Steps

### Step 1: Load Portfolio Overview
**User action**: Opens the Investments tab.
**System response**: The API queries `holdings` for this user, joined with `instruments` for name/type/currency. For each holding:
- `current_value` — last computed by valuation workflow
- `total_invested` — sum of purchase amounts
- `units` and `current_price`
- `last_valued_at` — timestamp of last valuation

A portfolio total is computed: `SUM(fx.convert(current_value, instrument.currency, 'INR'))` for all holdings. Holdings in non-INR currencies are converted using the latest `fx_rates`.

### Step 2: View Holdings by Type
**User action**: None — the default view groups by instrument type.
**System response**: Holdings are grouped into sections:
- Stocks (NSE/BSE)
- Mutual Funds
- ETFs
- Fixed Deposits
- PPF / NPS
- Crypto
- Gold / SGB
- US Stocks
- Other

Each holding shows: name, units, current value (INR), gain/loss amount and %, and a `last_valued_at` indicator.

### Step 3: See Stale Valuation Warning
**User action**: None — automatic.
**System response**: If `last_valued_at` is more than 24 hours ago for a market-priced instrument, the holding shows a "Rate as of {timestamp}" indicator. The `fx` domain similarly surfaces stale FX rate warnings. This prevents the user from acting on outdated data without knowing it.

### Step 4: Tap a Holding for Detail
**User action**: Taps a specific holding.
**System response**: Detail view shows:
- Full instrument name, ISIN, exchange
- Units, avg_cost_per_unit, total_invested
- Current price, current value, unrealised gain/loss
- For FDs: rate, maturity date, maturity amount
- SIP registrations linked to this instrument (if any)
- Valuation history chart (from `valuation_snapshots`)

## Domains Involved
- **investments**: Owns `holdings`, `instruments`, `valuation_snapshots`.
- **fx**: `convert()` called to express non-INR holdings in INR for the portfolio total.

## Edge Cases & Failures
- **No valuations yet** (holding just created): `current_value = NULL`. Shows "Updating..." until the valuation workflow runs.
- **Market closed / weekend**: `MarketPriceFetchWorkflow` only runs during market hours. Last known price is shown with the `last_valued_at` timestamp. This is expected — not an error state.
- **Instrument delisted or data source unavailable**: `last_valued_at` falls behind. The "Rate as of {timestamp}" warning appears. The valuation workflow logs a warning but does not fail the entire run — it carries forward the last known price.

## Success Outcome
User sees an up-to-date view of their entire investment portfolio with current values, gain/loss, and composition across all instrument types.
