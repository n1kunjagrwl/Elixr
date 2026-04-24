# Business Intent: investments

## Why This Domain Exists

A user's financial picture is incomplete without knowing what they own. Salary comes in, expenses go out, and some of what's left goes into savings and investments. The investments domain tracks that last part — what the user holds across all instrument types, what they paid for it, and what it is worth today. For most users, this spans a mix of mutual funds, stocks, fixed deposits, and maybe some gold or crypto. The domain brings all of these into one portfolio view, with live prices where available and calculated valuations for instruments like FDs that don't trade on a market.

---

## What It Provides

- A **portfolio view** across all instrument types: Indian stocks (NSE/BSE), mutual funds, ETFs, Fixed Deposits, PPF, bonds, NPS, Sovereign Gold Bonds, physical gold, US stocks, and cryptocurrency.
- **Live price updates** for market-traded instruments (stocks, MFs, ETFs, crypto, gold, US stocks) — fetched every 15 minutes during market hours.
- **Calculated valuations** for non-market instruments (FD, RD, PPF, bonds, NPS) — computed daily using financial formulas.
- **Historical portfolio value** — a daily snapshot of total portfolio value, enabling charts of portfolio growth over time.
- **SIP detection** — when a debit transaction matches a registered SIP (amount, date, account), the user is notified and asked to confirm the link between the transaction and the SIP.
- **Manual holding entry** — users can add any investment they hold, not just ones that were detected from a bank statement.
- **FD details** — users can register Fixed Deposit details (principal, rate, tenure, compounding) and see the projected maturity amount.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Add holding | Searches for a fund or stock, enters units and purchase price | Holding is registered; live price fetching starts automatically. (If a holding for this instrument already exists, the system returns a conflict error. The user must edit the existing holding instead.) |
| Add fixed deposit | Enters FD bank, principal, rate, tenure, start date | FD is registered; current value is computed daily using compound interest formula |
| Register SIP | Picks an instrument, enters amount, frequency, debit day, bank account | SIP is registered; future debits matching this pattern trigger a confirmation prompt |
| Confirm SIP payment | Sees notification "₹5,000 debit looks like your Axis Midcap Fund SIP" | Taps confirm to link the transaction to the SIP record |
| View portfolio | Opens investments screen | Sees total portfolio value, individual holdings with current value and gain/loss |
| View history | Scrolls to portfolio chart | Sees portfolio value over time (daily snapshots) |
| View FD details | Taps a fixed deposit | Sees maturity date, projected maturity amount, accrued interest to date |

---

## User Stories

- As a user, I want to add my mutual fund holdings so I can see their current value in one place.
- As a user, I want my SIP debits to be automatically linked to the correct fund so I don't have to log each monthly instalment manually.
- As a user, I want to see how much my portfolio is worth today compared to what I invested.
- As a user, I want to see my portfolio value over the past year so I can judge whether my investments are growing.
- As a user, I want to add my Fixed Deposit so I can see when it matures and how much I'll receive.
- As a user, I want all my investments — MFs, stocks, FDs, gold — in one place so I don't have to check multiple apps.

---

## What It Does Not Do

- Does not connect to demat accounts, brokerage platforms, or mutual fund portals to fetch holdings automatically.
- Does not provide investment advice or recommendations.
- Does not calculate capital gains, tax implications, or XIRR/CAGR (those are out of scope for the current version).
- Does not track dividends or coupon payments as income automatically — the user would log those as manual earnings if needed.
- Does not model loans or EMIs as investments.
- Does not allow multiple holding records for the same instrument. Each instrument can appear at most once in a user's portfolio — adding more units means editing the existing holding, not creating a second entry.

---

## Key Constraint

Holdings and instruments are separated: many users can hold the same Infosys share — it is one row in the `instruments` table. Price is fetched once per instrument, not once per user who holds it. This keeps API call volume manageable as the user base grows.
