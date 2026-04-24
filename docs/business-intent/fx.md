# Business Intent: fx

## Why This Domain Exists

India-based users often hold foreign currency savings accounts (NRE/NRO), invest in US stocks or crypto, or travel abroad and use a card in a foreign currency. When the app needs to show total portfolio value or check a budget, it needs to convert everything to INR. Without a consistent, shared currency conversion service, each domain would either hardcode exchange rates, fetch them independently (incurring redundant API costs), or simply ignore multi-currency amounts. The fx domain solves this by providing one place to fetch, cache, and serve exchange rates for the entire app.

---

## What It Provides

- **Cached FX rates** — exchange rates for all relevant currency pairs, refreshed every 6 hours from a live API and stored in the database.
- **Currency conversion** — a single `convert(amount, from, to)` call that any domain can use to get amounts in a consistent currency.
- **Historical rate lookup** — when displaying the value of a past transaction in today's terms, callers can request the rate that was in effect closest to a specific date.

---

## How a User Interacts With It

The user never interacts with the fx domain directly. It is infrastructure that makes multi-currency amounts transparent throughout the app:

| Where it appears | What the user sees |
|---|---|
| Portfolio screen | All investments displayed in INR, regardless of the instrument's trading currency |
| Budget tracking | A USD-denominated credit card transaction converted to INR before being counted against a budget |
| Transaction list | Foreign currency transactions shown with their INR equivalent |
| Earnings summary | Foreign income converted to INR for totals |

---

## User Stories (via other domains)

- As a user, I want to see my US stock holdings valued in INR so I can compare them against my Indian investments.
- As a user, I want my budget totals to include spending on my forex credit card, converted to INR.
- As a user, I want to see a consistent INR figure for my total portfolio even though some holdings are in USD or crypto.

---

## What It Does Not Do

- Does not expose any user-facing screens or settings. There is no "FX settings" page.
- Does not allow users to set custom exchange rates or lock rates for specific transactions.
- Does not support real-time tick-level rates. A 6-hour refresh is accurate enough for personal finance tracking.
- Does not store historical rate series for arbitrary past dates — only current rates are maintained, with partial history available through the scheduled fetches.

---

## Key Constraint

All rates are stored and triangulated through INR as the base currency. Conversion between two non-INR currencies (e.g., USD to EUR) is computed as USD→INR→EUR. This keeps the rate table simple (one row per currency-to-INR pair) and naturally suits the app's primary audience, whose reference currency is always INR.
