# Business Intent: accounts

## Why This Domain Exists

Before a user can upload a statement or log a transaction, they need to tell the app which account that money came from. The accounts domain provides the naming layer — it lets users label their bank accounts and credit cards so that transactions have a meaningful source. It also tracks which date ranges have already been imported, so the app can warn the user before they accidentally import the same period twice.

---

## What It Provides

- A way to **register a bank account label** (e.g., "HDFC Savings") so statements and transactions can be attributed to it.
- A way to **register a credit card label** (e.g., "HDFC Millennia") with billing cycle information.
- A way to **update** account details (nickname, metadata).
- A way to **deactivate** an account so it stops appearing in the UI without losing the transaction history linked to it.
- Provides the account identity (`account_id`) used by the `statements` domain to detect whether a new upload overlaps a previously imported date range for the same account.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Add bank account | Fills in bank name, account type, last 4 digits | Account label is created; user is nudged to upload a statement |
| Add credit card | Fills in bank name, card network, last 4, billing cycle day | Card label is created; user is nudged to upload a statement |
| Edit account | Updates nickname or metadata | Account details are updated |
| Deactivate account | Chooses to remove an account from active view | Account is hidden; linked transactions and statements are preserved |
| Reactivate an account | Navigates to "Inactive accounts" and restores a previously deactivated account | `is_active = true` is restored. The account reappears in all active UI lists. SIP registrations that were deactivated when the account was removed are NOT automatically re-enabled — the user must re-enable each SIP manually. |

---

## User Stories

- As a user, I want to add my HDFC savings account so I can upload my bank statement against it.
- As a user, I want to add my credit card so I can track card expenses separately from bank expenses.
- As a user, I want to give my accounts meaningful nicknames so I can tell them apart at a glance.
- As a user, I want to deactivate an old account I no longer use without losing the history of transactions from that account.
- As a user, I want to be warned if I upload a statement for a date range I've already imported, so I don't create duplicate transactions.

---

## What It Does Not Do

- Does not connect to any bank. There is no live balance sync, no open banking API, no account aggregation.
- Does not track current balances. Elixir is an expense tracker, not a balance reconciler.
- Does not store full account numbers. Only the last 4 digits are kept.
- Does not support joint accounts. Every account is owned by exactly one user.
- Does not automatically re-enable SIP registrations when an account is reactivated. The user must re-enable them from the Investments screen.

---

## Key Constraint

An account label is just a name. Its only job is to give transactions a human-readable source and to carry the metadata needed to warn about duplicate statement imports. It implies nothing about the account's actual balance in the bank.
