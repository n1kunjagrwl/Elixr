# Business Intent: transactions

## Why This Domain Exists

All financial tracking in Elixir ultimately rests on a complete, accurate record of money moving in and out. The transactions domain is that record — it stores every debit, credit, and transfer the user has ever imported or entered, and makes the data available to every other domain that needs to aggregate or analyse it. Without it, budgets have nothing to count, earnings have nothing to classify, and investment detection has no signals to work from.

---

## What It Provides

- A **ledger** of all financial movements: every transaction from statement uploads, CSV imports, and manual entries lives here.
- **Manual transaction entry** for users who want to log a cash purchase or a transaction that did not appear in a statement.
- **Transaction editing** — the user can correct a category, change the type (expense/income/transfer), add notes, or split the amount across multiple categories after the fact.
- **Item-level breakdowns** — a single transaction (e.g., an Amazon order) can be split into multiple items, each with its own category and label.
- **Duplicate prevention** — the same transaction can never appear twice, even if the user uploads the same statement twice.
- **Recurring transaction detection** — a weekly background job identifies patterns (same merchant, consistent interval) and labels those transactions so the user can see their subscriptions and recurring bills at a glance.
- **Transfer detection** — when the same amount moves between two of the user's accounts on close dates, both transactions are automatically labelled as a self-transfer so they don't pollute expense or income totals.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| View transactions | Opens the transaction list | Sees all transactions sorted by date, with category and account |
| Add manually | Taps "Add transaction" and fills in amount, date, account, category | Transaction is saved and immediately counted in budgets and earnings |
| Edit transaction | Taps a transaction and changes its category | Budget totals are retroactively corrected; updated category is saved |
| Split transaction | Edits a transaction to assign different amounts to different categories | Item breakdown is saved; each category gets its own budget contribution |
| Add item labels | Edits a transaction to name what was bought | Labels are stored alongside the category for personal reference |
| Add notes | Edits a transaction to add a note ("reimbursable from company") | Note is visible in the transaction detail view |
| Review recurring pattern | Sees a "recurring" badge on a Netflix charge | Knows the system has detected a subscription pattern |
| Review transfer | Sees a "transfer" label on a ₹50,000 debit and credit on the same day | Knows both sides are excluded from expenses and income |

---

## User Stories

- As a user, I want to see all my transactions in one place so I can understand my complete financial picture.
- As a user, I want to add a cash transaction manually so my records are complete even when it doesn't appear in a bank statement.
- As a user, I want to correct the category of a transaction so my budgets and spending summaries are accurate.
- As a user, I want to split an Amazon order across "Electronics" and "Groceries" so each category reflects only what I actually spent on it.
- As a user, I want transfers between my own accounts to be excluded from my expense totals so my spending doesn't look inflated.
- As a user, I want the system to identify recurring charges like subscriptions so I can see them without having to search.
- As a user, I want to be protected from duplicates if I accidentally upload the same statement twice.

---

## What It Does Not Do

- Does not make categorisation decisions. It stores the results of categorisation performed by the `statements` or `import_` workflows, or provided directly by the user.
- Does not compute balances. Elixir is not a balance sheet tool.
- Does not connect to banks. Transactions come from uploaded statements, CSV imports, or manual entry only.
- Does not delete transactions. Once a transaction exists it can only be edited, not removed (to preserve ledger integrity).

---

## Key Constraint

The transaction ledger is the single source of truth for all money in Elixir. Every domain that needs to know "how much did the user spend on X?" asks this domain, via the `transactions_with_categories` view, rather than storing their own copy of the data.
