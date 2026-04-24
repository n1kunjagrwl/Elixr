# Business Intent: earnings

## Why This Domain Exists

Most personal finance tools treat every bank credit as income. They are wrong. A credit can be a salary, a freelance payment, a rental deposit, interest from an FD — or it can be a friend paying back their share of dinner. Only the first group counts as income. The earnings domain exists to make this distinction, so the user can see what they actually earn, broken down by source and type.

---

## What It Provides

- **Automatic income detection** — when a bank credit arrives via statement upload, the system checks whether it looks like income (salary keyword, consistent monthly amount, known employer name). If it does, it is recorded as an earning automatically.
- **Ambiguous credit classification** — when the system cannot confidently determine whether a credit is income or a peer repayment, it asks the user to decide. The user is not left with an inflated or deflated income figure because the system guessed wrong.
- **Manual income entry** — users can log income that has no corresponding bank transaction: cash earnings, foreign wire transfers not yet in a statement, ad-hoc freelance payments.
- **Income source labels** — users can create named sources (e.g., "Think41 Salary", "Freelance — Acme Corp") so income can be tracked and compared by origin over time.
- **Income by type** — salary, freelance, rental, dividend, interest, business, and other are tracked as distinct types, enabling summaries like "total freelance income this year".

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| View income | Opens earnings summary | Sees total income by month, broken down by source type |
| Classify ambiguous credit | Taps notification "A ₹45,000 credit — is this income or a repayment?" | User selects "Salary — Think41" or "Peer repayment" or "Ignore". If the user selects "Peer repayment", they can optionally link it to an existing open peer balance, recording it as a settlement in the `peers` domain at the same time. |
| Add manual earning | Taps "Add income" and fills in amount, date, source type | Earning is recorded without a linked bank transaction |
| Create earning source | Names a recurring income source (e.g., "Consulting — XYZ Ltd") | Future income of that type can be attributed to the named source |
| Deactivate earning source | Marks a source as inactive | Source no longer appears in manual entry dropdowns |

---

## User Stories

- As a user, I want my salary to be recognised automatically so I don't have to manually mark it as income every month.
- As a user, I want to be asked when a credit is ambiguous so my income figure is accurate, not inflated by peer repayments.
- As a user, I want to log a cash payment I received so my income picture includes it even though it won't appear in a bank statement.
- As a user, I want to see how much I earned from freelance work this year separately from my salary.
- As a user, I want to track income from multiple sources so I can understand which parts of my income are growing or shrinking.

---

## What It Does Not Do

- Does not automatically detect peer repayments and mark them as settled. That is the `peers` domain's responsibility, with explicit user action.
- Does not track income tax, TDS, or net-vs-gross. Elixir records what arrives in the bank, not what was deducted before.
- Does not link earnings to budgets or savings goals. Earnings are informational — the user sees them as a separate income view, not as a budget input.
- Does not retroactively reclassify previously labelled income if the user changes their mind about a source type.
- Does not deduplicate manually entered earnings. Unlike transactions (which use a fingerprint), two manual earnings with the same amount, date, and source can be created independently. The UI warns but does not block duplicate entries.

---

## Key Constraint

The system never auto-classifies an ambiguous credit as income. Peer repayments and income look identical at the DB level (a credit with a description). The consequences of getting it wrong — inflated income figures — are worse than the cost of asking. When in doubt, ask the user.
