# Business Intent — Elixir

Elixir is a personal finance PWA for Indian users. It answers one question: **where does my money come from and where does it go?** The 12 domains below each own a distinct slice of that answer.

This directory exists to describe each domain from the user's perspective — what it provides, why it exists, and what a user can accomplish through it. It is the starting point for identifying gaps, inconsistencies, and missing user stories before any code is written.

---

## Domain Overview

| Domain | One-line intent |
|---|---|
| [identity](identity.md) | Lets a user register with their phone number and sign in securely |
| [accounts](accounts.md) | Lets a user name and organise their bank accounts and credit cards |
| [statements](statements.md) | Turns an uploaded bank or card statement into a list of categorised transactions |
| [transactions](transactions.md) | Stores every financial movement the user has ever recorded |
| [categorization](categorization.md) | Organises transactions into categories the user recognises and controls |
| [earnings](earnings.md) | Separates income from all other credits so the user understands what they earn |
| [investments](investments.md) | Tracks what the user owns across stocks, funds, FDs, and other instruments |
| [budgets](budgets.md) | Lets the user set spending limits and alerts them when those limits are approached or crossed |
| [peers](peers.md) | Tracks money owed to and from friends, family, and colleagues |
| [notifications](notifications.md) | Keeps the user informed about anything in the app that needs their attention |
| [fx](fx.md) | Converts foreign currency amounts to INR so everything can be shown in one currency |
| [import_](import_.md) | Lets the user bring in historical data from a spreadsheet or generic CSV |

---

## Application Flow (first-run to steady state)

```
Register → Add account label → Upload statement (or log manually)
  → AI classifies transactions → User reviews & confirms
    → Transactions feed budgets, earnings, and investment detection
      → Notifications surface anything needing attention
```

Every domain plays a role somewhere in this chain. The business intent files describe each role in plain terms.
