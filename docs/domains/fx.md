# Domain: fx

## Responsibility

Caches foreign exchange rates and exposes a currency conversion utility that any other domain can call. The `fx` domain fetches rates from exchangerate-api.com on a schedule via a Temporal workflow and stores them in its own table. At request time, conversion is a DB lookup — no live API call.

This domain exists because multiple domains need currency conversion (investments portfolio in INR, multi-currency bank accounts, transaction display) and all of them should use the same rate source and cache. Keeping it as a dedicated domain ensures there is exactly one place to update when the rate source changes.

---

## Tables Owned

### `fx_rates`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `from_currency` | `char(3)` NOT NULL | ISO 4217 code e.g. `USD` |
| `to_currency` | `char(3)` NOT NULL | ISO 4217 code e.g. `INR` |
| `rate` | `numeric(18,6)` NOT NULL | 1 unit of `from_currency` = `rate` units of `to_currency` |
| `fetched_at` | `timestamptz` NOT NULL | When this rate was fetched from the API |

Unique constraint: `(from_currency, to_currency)` — one current rate per pair, upserted on each refresh.

No `outbox` table — the fx domain does not publish domain events.

---

## SQL Views Exposed

None. Other domains call the `convert()` service method directly (Pattern 3, justified because conversion is synchronous and stateless).

---

## Events Published

None.

---

## Events Subscribed

None.

---

## Temporal Workflow

### `FXRateRefreshWorkflow`

See [workflows/fx-rate-refresh.md](../workflows/fx-rate-refresh.md).

Scheduled every 6 hours. Fetches rates for all non-INR currencies present in `bank_accounts`, `credit_cards`, and `instruments`, plus a fixed set of common currencies (USD, EUR, GBP, SGD, AED). Upserts into `fx_rates`.

---

## Service Methods Exposed

### `convert(amount, from_currency, to_currency, as_of_date?) → Decimal`

The only cross-domain service call in the `fx` domain. Returns the converted amount using the latest cached rate for the currency pair.

```python
def convert(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    as_of_date: date | None = None,   # if provided, use the rate fetched closest to that date
) -> Decimal:
    ...
```

If `from_currency == to_currency`, returns `amount` unchanged.

If no rate is found for the pair, raises `FXRateUnavailableError` with the currencies and the last available rate's timestamp — callers decide how to handle stale data.

**INR as base**: All rates are stored relative to INR (USD→INR, EUR→INR, etc.). For non-INR pairs (USD→EUR), the conversion is triangulated: `amount_eur = amount_usd * (INR/USD rate) / (INR/EUR rate)`.

---

## Key Design Decisions

**Rates cached in DB, not in memory.** Storing in PostgreSQL means rates survive server restarts, are accessible to all workers, and can be queried historically (if ever needed). An in-memory cache would require a warm-up after restart and wouldn't be shared across multiple server instances.

**6-hour refresh interval.** FX rates change continuously, but for personal finance tracking, 6-hour accuracy is more than sufficient. For investment portfolio valuation, a slightly stale FX rate (e.g., 4 hours old) does not meaningfully change the user's financial picture.

**Rate staleness is surfaced, not silently used.** `as_of_date` allows callers to request the rate at a specific point in time for historical transaction display. When a rate is more than 24 hours old and `as_of_date` is not provided, the service logs a warning — the UI can display "rate as of {fetched_at}" to inform the user.

**Triangulation through INR.** Storing INR as the base currency simplifies the rate table (only N pairs instead of N² pairs) and aligns with the application's primary currency. Indian users primarily convert foreign currencies to INR, making this the natural base.
