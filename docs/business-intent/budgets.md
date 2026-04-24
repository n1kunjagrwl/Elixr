# Business Intent: budgets

## Why This Domain Exists

Tracking past spending is useful. Controlling future spending is better. The budgets domain lets users commit to spending limits for specific categories — "I will spend no more than ₹8,000 on Food & Dining this month" — and then enforces those limits passively as transactions flow in. The user doesn't have to check in manually; the system alerts them before they cross the line, and again if they do.

---

## What It Provides

- A way to **set a spending limit** for any expense category for a time period (month, week, or a custom date range).
- **Real-time progress tracking** — every time a relevant transaction is categorised, the running total for that budget is updated automatically.
- **80% warning alert** — notified when the user is approaching their limit.
- **100% breach alert** — notified when the user has crossed their limit.
- **Salary-aligned budget periods** — a user paid on the 15th can set their monthly budget to run 15th–14th rather than 1st–31st, so the numbers match how they actually think about their money.
- **Retroactive correction** — if the user re-categorises a transaction after the fact, the relevant budget totals are corrected automatically.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Create budget | Picks a category, sets a limit, picks period type | Budget goal is created; progress tracking starts immediately |
| View budget status | Opens budget screen | Sees each category's spend vs. limit as a progress bar |
| Get 80% alert | (Passive) | Notification: "You've used 82% of your Food & Dining budget this month" |
| Get breach alert | (Passive) | Notification: "You've exceeded your Shopping budget by ₹1,200" |
| Edit budget | Changes the limit on an existing budget goal | New limit is applied from the current period |
| Deactivate budget | Turns off a budget they no longer want to track | Budget stops tracking; no further alerts for that category |
| Re-categorise a transaction | Edits a transaction to change its category | Budget for the old category is decremented; budget for the new category is incremented |

---

## User Stories

- As a user, I want to set a ₹8,000 monthly limit on Food & Dining so I can keep my restaurant spending in check.
- As a user, I want to be warned before I exceed my budget so I can adjust my spending while there's still time.
- As a user, I want to know immediately when I've crossed a budget limit so I can make a conscious decision about whether to continue spending.
- As a user, I want my budget period to align with my salary date so it reflects how I actually manage my money each pay cycle.
- As a user, I want my budget totals to update automatically when I categorise a transaction, not just at the end of the month.
- As a user, I want budget totals to self-correct if I change a transaction's category.

---

## What It Does Not Do

- Does not block transactions or prevent the user from spending beyond a limit. Budgets are informational and advisory only.
- Does not carry over unspent amounts to the next period (rollover is reserved for a future version).
- Does not create budgets for income categories or transfer categories. Budgets are expense-only.
- Does not provide budget recommendations or suggest appropriate limits based on past spending.
- Does not aggregate budgets across multiple users or accounts in a shared view.
- Does not backfill historical transactions when a budget is created. A budget created mid-period starts tracking from zero — transactions already in the ledger for the current period are not counted retroactively. Only transactions categorised after the budget goal is created contribute to its progress.

---

## Key Constraint

Budget progress is maintained as a running counter updated by events, not computed on the fly from the transaction table. This makes the budget dashboard a single fast lookup, not a potentially slow aggregation query across potentially thousands of transactions.
