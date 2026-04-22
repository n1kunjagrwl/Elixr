# Domain: investments

## Responsibility

Manages the user's investment portfolio across all instrument types: Indian stocks (NSE/BSE), mutual funds, ETFs, Fixed Deposits, PPF, bonds, NPS, Sovereign Gold Bonds, physical gold, US stocks, and cryptocurrency. It tracks what the user holds, what they paid for it, and what it is worth today. Valuations are kept current by Temporal scheduled workflows — market-priced instruments via live API calls, non-market instruments (FD, PPF, bonds) via financial formulas calculated on a schedule.

The domain also detects SIP (Systematic Investment Plan) debits arriving via bank statement — when a debit matches a registered SIP amount and frequency, the user is asked to confirm the link.

---

## Tables Owned

### `instruments`
The master registry of all investable instruments known to the system.

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `ticker` | `text` | NSE/BSE symbol, AMFI scheme code, CoinGecko ID, or internal identifier |
| `isin` | `text` NULLABLE | ISIN code where applicable |
| `name` | `text` NOT NULL | Full name e.g. "HDFC Top 100 Fund — Growth" |
| `type` | `text` NOT NULL | `stock` \| `mf` \| `etf` \| `fd` \| `ppf` \| `bond` \| `nps` \| `sgb` \| `crypto` \| `gold` \| `us_stock` \| `rd` \| `other` |
| `exchange` | `text` NULLABLE | `NSE` \| `BSE` \| `NYSE` \| `NASDAQ` \| `MCX` |
| `currency` | `char(3)` NOT NULL | Primary trading currency |
| `data_source` | `text` NULLABLE | Which API client provides prices (`amfi`, `eodhd`, `coingecko`, `twelve_data`, `metals_api`, `calculated`) |
| `govt_rate_percent` | `numeric(6,3)` NULLABLE | For PPF/NPS: current government-declared interest rate |
| `created_at` | `timestamptz` | — |

### `holdings`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `instrument_id` | `uuid` FK → `instruments.id` | — |
| `units` | `numeric(20,6)` | Number of units / shares / grams (6 decimal places for MF units) |
| `avg_cost_per_unit` | `numeric(15,4)` | Weighted average cost |
| `total_invested` | `numeric(15,2)` | Total cash invested (sum of all purchase amounts) |
| `current_value` | `numeric(15,2)` | Last computed value = `units × current_price` |
| `current_price` | `numeric(15,4)` | Last known price per unit |
| `last_valued_at` | `timestamptz` | When `current_value` was last updated |
| `created_at` | `timestamptz` | — |

### `sip_registrations`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `instrument_id` | `uuid` FK → `instruments.id` | Which fund/stock this SIP is for |
| `amount` | `numeric(15,2)` NOT NULL | Expected debit amount per instalment |
| `frequency` | `text` NOT NULL | `monthly` \| `weekly` \| `quarterly` |
| `debit_day` | `int` | Day of month (for monthly SIPs) |
| `bank_account_id` | `uuid` | → `bank_accounts.id` (no PG FK) — which account the debit comes from |
| `is_active` | `bool` DEFAULT true | — |
| `created_at` | `timestamptz` | — |

### `valuation_snapshots`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `holding_id` | `uuid` FK → `holdings.id` | — |
| `price` | `numeric(15,4)` | Price per unit at snapshot time |
| `value` | `numeric(15,2)` | Total value of holding at snapshot time |
| `snapshot_date` | `date` | — |

One row per holding per day. Used to render historical portfolio value charts. The valuation workflow upserts by `(holding_id, snapshot_date)` — only one snapshot per holding per day.

### `fd_details`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `holding_id` | `uuid` FK → `holdings.id` | — |
| `principal` | `numeric(15,2)` NOT NULL | Amount deposited |
| `rate_percent` | `numeric(6,3)` NOT NULL | Annual interest rate |
| `tenure_days` | `int` NOT NULL | Total FD tenure |
| `start_date` | `date` NOT NULL | FD opening date |
| `maturity_date` | `date` NOT NULL | Computed: `start_date + tenure_days` |
| `compounding` | `text` NOT NULL | `monthly` \| `quarterly` \| `annually` \| `simple` |
| `maturity_amount` | `numeric(15,2)` | Computed at creation |

### `outbox`
Standard outbox table.

---

## SQL Views Exposed

None. Portfolio data is not consumed via cross-domain view by other domains.

---

## Events Published

### `SIPDetected`
```python
@dataclass
class SIPDetected:
    event_type = "investments.SIPDetected"
    transaction_id: UUID
    user_id: UUID
    sip_registration_id: UUID
    amount: Decimal
    instrument_name: str
```
Consumed by: `notifications` (asks user to confirm the SIP link)

### `ValuationUpdated`
```python
@dataclass
class ValuationUpdated:
    event_type = "investments.ValuationUpdated"
    user_id: UUID
    updated_holding_ids: list[UUID]
    total_portfolio_value: Decimal
```

### `SIPLinked`
```python
@dataclass
class SIPLinked:
    event_type = "investments.SIPLinked"
    transaction_id: UUID
    sip_registration_id: UUID
    user_id: UUID
```

---

## Events Subscribed

### `AccountRemoved` (from `accounts`)

When a bank account label is removed by the user, deactivate any SIP registrations linked to it:

```
For each sip_registration where bank_account_id = event.account_id AND is_active = true:
  UPDATE sip_registrations SET is_active = false
```

SIP detection compares incoming debits against active registrations only. Deactivating the registration ensures no false-positive SIP alerts are generated for an account the user considers gone. The holding itself is not affected — the user still owns the investment.

Handler must be idempotent: setting `is_active = false` on an already-inactive row is a no-op.

### `TransactionCreated` (from `transactions`)

When a debit transaction arrives, the handler checks if it matches any active SIP registration for this user:

```
For each active sip_registration for this user:
  - Does the debit amount match sip_registration.amount (±2%)?
  - Does the transaction date fall within ±3 days of the expected debit_day?
  - Does the bank_account_id match?

If match found:
  → Publish SIPDetected (user confirms or dismisses via the notification)

If no match:
  → Skip (not an SIP transaction)
```

---

## Temporal Workflows

### `MarketPriceFetchWorkflow` (scheduled every 15 minutes during market hours)

See [workflows/investment-valuation.md](../workflows/investment-valuation.md).

Fetches live prices for: `stock`, `etf`, `mf`, `crypto`, `gold`, `us_stock`, `sgb`.

### `CalculatedValuationWorkflow` (scheduled daily at 00:30 IST)

Computes current value for non-market instruments:

| Type | Formula |
|---|---|
| `fd` | `P × (1 + r/n)^(n×t)` where `n` = compoundings per year, `t` = years elapsed |
| `rd` | Sum of monthly deposits each compounded for remaining tenure |
| `ppf` | Cumulative deposits × `govt_rate_percent` (rate from `instruments.govt_rate_percent`) |
| `bond` | Face value + accrued interest (coupon rate × days elapsed / 365) |
| `nps` | NAV × units (NAV fetched from fund manager if available, else carried forward) |

---

## Key Design Decisions

**`instruments` is a shared master table, not per-user.** Two users holding Infosys shares reference the same `instruments` row. Price fetching is done once per instrument, not once per holding — this avoids redundant API calls as user count grows.

**`fd_details` as a separate table rather than JSONB.** FD parameters (rate, tenure, compounding) are structured and queried frequently by `CalculatedValuationWorkflow`. A separate normalised table is more efficient and explicit than a JSONB blob.

**`valuation_snapshots` for historical charts.** Storing one snapshot per holding per day means a portfolio value chart for any time range is a simple aggregation query on `valuation_snapshots`, without replaying any API calls or formulas. The slight storage cost is worth the query simplicity.

**SIP detection with ±2% amount and ±3-day window.** SIP amounts can vary slightly (bank rounding) and debit timing shifts when the scheduled date falls on a holiday. The tolerances are narrow enough to avoid false positives while catching real SIP debits reliably.
