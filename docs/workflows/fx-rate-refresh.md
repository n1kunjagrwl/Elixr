# Workflow: FXRateRefreshWorkflow

**Domain**: `fx`  
**Trigger**: Temporal schedule — every 6 hours  
**Schedule**: 00:00, 06:00, 12:00, 18:00 IST  

---

## Purpose

Keeps the `fx_rates` table current so that any domain needing a currency conversion gets a rate that is at most 6 hours stale. This workflow is simple and has no human interaction — it runs, fetches, stores, and exits.

---

## Step-by-step

```
1. Determine currencies to fetch:
   Query to find all non-INR currencies in active use:
     SELECT DISTINCT currency FROM bank_accounts WHERE currency != 'INR'
     UNION
     SELECT DISTINCT currency FROM credit_cards WHERE currency != 'INR'
     UNION
     SELECT DISTINCT currency FROM instruments WHERE currency != 'INR'

   Always include this fixed baseline set regardless of user data:
     USD, EUR, GBP, SGD, AED, JPY, CHF, CAD, AUD, HKD

2. Activity: fetch_fx_rates(currencies: list[str])
   Source: exchangerate-api.com
   Endpoint: GET /v6/{api_key}/latest/INR
   Response: { base: "INR", rates: { USD: 0.01194, EUR: 0.01098, ... } }

   The API returns rates where INR is the base (1 INR = X foreign currency).
   Invert to get: 1 foreign currency = Y INR.
   e.g., if rates.USD = 0.01194, then 1 USD = 1/0.01194 = 83.75 INR

3. For each currency in the response:
   UPSERT INTO fx_rates (from_currency, to_currency, rate, fetched_at)
   VALUES ('{currency}', 'INR', {rate}, now())
   ON CONFLICT (from_currency, to_currency) DO UPDATE
     SET rate = excluded.rate, fetched_at = excluded.fetched_at

4. Also store the inverse rates (INR → foreign) for completeness:
   UPSERT INTO fx_rates ('INR', '{currency}', {1/rate}, now())

5. Workflow completes successfully
```

---

## Error Handling

```
Activity retry policy:
  maximum_attempts: 5
  initial_interval: 30s
  backoff_coefficient: 2.0
  maximum_interval: 10min

If all 5 attempts fail:
  → Log error with last_fetched_at of existing rates
  → Workflow completes with failure (Temporal marks it failed in UI)
  → Existing rates in fx_rates remain — no rows are deleted or invalidated
  → The fx.convert() service method will use the last known rate
  → If the last known rate is older than 24 hours, convert() logs a warning
```

The system is designed to degrade gracefully — stale FX rates are better than no rates. A 6-hour stale rate for displaying INR equivalents in a personal finance app is fully acceptable.

---

## Triangulation for Non-INR Pairs

The `fx.convert()` service method handles conversion between two non-INR currencies by triangulating through INR:

```python
def convert(amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    if from_currency == to_currency:
        return amount
    if to_currency == 'INR':
        rate = fetch_rate(from_currency, 'INR')  # stored directly
        return amount * rate
    if from_currency == 'INR':
        rate = fetch_rate('INR', to_currency)    # stored directly
        return amount * rate
    # Non-INR pair: triangulate
    from_to_inr = fetch_rate(from_currency, 'INR')
    inr_to_target = fetch_rate('INR', to_currency)
    return amount * from_to_inr * inr_to_target
```

This avoids needing to store N² rate pairs. All conversions go through INR as the hub.

---

## Notes

The `FXRateRefreshWorkflow` is registered as a Temporal scheduled workflow with a cron expression. It is not triggered by any application event. The Temporal server manages the schedule — even if the application server is down during a scheduled run, Temporal will fire the workflow when the server comes back online.

Monitoring: if `fx_rates.fetched_at` for any active currency is older than 12 hours, the application health check endpoint should return a warning (not an error — stale rates don't break functionality).
