# Workflow: Investment Valuation

**Domain**: `investments`  
**Two workflows**: `MarketPriceFetchWorkflow` and `CalculatedValuationWorkflow`  
**Trigger**: Temporal schedule (both)  

---

## Purpose

Keeps portfolio valuations current. Market-priced instruments (stocks, MFs, ETFs, crypto, gold, US stocks) are updated via live API calls. Non-market instruments (FDs, PPF, bonds, RDs) are updated by computing their current value from their stored terms and elapsed time.

The two workflows are separate because they have different schedules, different data sources, and different failure modes.

---

## Workflow 1: MarketPriceFetchWorkflow

**Schedule**: Every 15 minutes during Indian market hours (09:15–15:30 IST Mon–Fri); every 6 hours otherwise

### Step-by-step

```
1. Fetch all distinct (instrument_id, data_source) pairs where:
   - There exist active holdings for any user
   - instruments.type IN ('stock', 'mf', 'etf', 'crypto', 'gold', 'us_stock', 'sgb')

2. Group by data_source:

   AMFI (mutual funds):
     - Fetch https://www.amfiindia.com/spages/NAVAll.txt (full NAV file)
     - Parse: pipe-delimited, find rows matching instruments.ticker (AMFI scheme code)
     - Extract NAV and NAV date
     - Skip if NAV date has not changed since last snapshot

   Eodhd (NSE/BSE stocks and ETFs):
     - Batch request: up to 50 tickers per call
     - GET /real-time/{tickers}?api_token={key}&fmt=json
     - Extract: close price, timestamp
     - If market closed (weekend/holiday): use previousClose

   CoinGecko (crypto):
     - GET /simple/price?ids={coingecko_ids}&vs_currencies=inr,usd
     - Match by instruments.ticker (CoinGecko coin ID)
     - Store INR price directly

   Twelve Data (US stocks):
     - Batch request: GET /price?symbol={symbols}&apikey={key}
     - US market hours: 19:30–01:30 IST (next day)
     - Outside hours: use last close price
     - Convert USD → INR using latest fx_rates

   metals-api (gold):
     - GET /latest?base=INR&symbols=XAU
     - Convert troy-ounce price to per-gram: price / 31.1035
     - For SGBs: use this price for current valuation

3. For each instrument with a new price:
   a. Update all holdings of this instrument:
      holdings.current_price = new_price
      holdings.current_value = units * new_price
      holdings.last_valued_at = now()

   b. Upsert valuation_snapshots:
      INSERT INTO valuation_snapshots (holding_id, price, value, snapshot_date)
      VALUES (...)
      ON CONFLICT (holding_id, snapshot_date) DO UPDATE
        SET price = excluded.price, value = excluded.value
      -- one snapshot per holding per day; intraday updates overwrite

4. Publish ValuationUpdated event (one per user with updated holdings)
```

### Error Handling

| Failure | Behaviour |
|---|---|
| AMFI file unavailable | Log warning, retain previous NAV. Do not fail other sources. |
| Eodhd API rate limit | Exponential backoff, retry up to 3 times. If still failing, mark affected holdings `stale`. |
| CoinGecko rate limit | Same as Eodhd |
| Twelve Data API error | Retain last price. Convert retained price with latest FX rate. |
| Instrument has no data_source | Skip silently — user-created instruments may not have a source configured |

Each data source fetch is a separate Temporal activity, so a failure in one source does not block updates from other sources.

---

## Workflow 2: CalculatedValuationWorkflow

**Schedule**: Daily at 00:30 IST

### Supported instrument types and formulas

**Fixed Deposit (`fd`)**
```
n = compoundings_per_year  (monthly=12, quarterly=4, annually=1, simple=0)
t = days_elapsed / 365

If n > 0 (compound):
  maturity = principal × (1 + rate/100/n)^(n×t)
  current_value = maturity (projected value if held to maturity)

If n == 0 (simple):
  current_value = principal × (1 + rate/100 × t)

For display: also compute maturity_amount and days_remaining
```

**Recurring Deposit (`rd`)**
```
Each monthly instalment is compounded for the remaining tenure.
current_value = Σ [instalment × (1 + rate/100/12)^(months_remaining_for_this_instalment)]
```

**PPF**
```
rate = instruments.govt_rate_percent (updated annually when government announces rate)
current_value = Σ [annual_deposit × (1 + rate/100)^years_since_deposit]
```

**Bond**
```
days_elapsed = today - issue_date
accrued_interest = face_value × coupon_rate/100 × days_elapsed/365
current_value = face_value + accrued_interest
```

**NPS**
```
If NAV is available from pension fund manager API:
  current_value = units × current_nav
Else:
  Carry forward previous current_value (NPS NAV not always publicly available)
```

### Step-by-step

```
1. Fetch all holdings where instrument.type IN ('fd', 'ppf', 'bond', 'nps', 'rd')
   for all users

2. For each holding:
   a. Load instrument details + fd_details (if applicable)
   b. Apply the appropriate formula above
   c. Update holdings.current_value, holdings.last_valued_at
   d. Upsert valuation_snapshots (same as MarketPriceFetchWorkflow)

3. Publish ValuationUpdated per user

4. Log any holdings where maturity_date < today:
   - FD has matured but no manual update recorded
   - Send a notification: "Your FD with {bank} matured on {date} — did you renew or redeem it?"
```

### Error Handling

Calculated valuations are deterministic — they cannot fail due to external API issues. The only failure mode is missing data (e.g., `fd_details` not found for an FD holding). These are logged and skipped; the holding retains its previous `current_value`.

---

## valuation_snapshots Retention

Snapshots accumulate one row per holding per day. For a user with 10 holdings tracked for 2 years, this is ~7,300 rows — small and fast to query.

No automatic pruning. If storage becomes a concern at scale, snapshots older than 5 years can be aggregated to weekly granularity (one row per week instead of one per day) without meaningfully impacting chart resolution.
