# Business Intent: peers

## Why This Domain Exists

Informal money flows between friends, family, and colleagues are a normal part of most people's financial lives — splitting a dinner bill, covering a friend's share of a trip, lending someone money. These flows don't fit neatly into expense or income categories, and they create obligations that need to be tracked until settled. The peers domain provides a simple ledger for exactly this: who owes what to whom, and what has already been paid back.

---

## What It Provides

- A way to **add peer contacts** — people the user frequently splits money with — so balances can be associated with named individuals.
- A way to **log a balance** — a record that a specific person owes the user money (or vice versa) for a specific reason.
- A way to **record settlements** — partial or full payments that reduce an outstanding balance.
- **Running balance tracking** — the domain maintains `remaining_amount` automatically as settlements are added, and updates the balance status (`open` → `partial` → `settled`).
- **Transaction linking** — optionally, a balance or settlement can be linked to a specific bank transaction, allowing the user to see the bank record alongside the peer ledger record.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Add peer | Enters a name and optional phone number | Contact is saved for future use |
| Log a balance | Picks a peer, enters amount, direction (owed to me / I owe), and description | Balance is created with status "open" |
| Record settlement | Taps "Settle" on an open balance, enters amount paid | Settlement is logged; remaining amount is recalculated; status updates |
| View peer summary | Opens peers screen | Sees total owed to them and total they owe, with per-peer breakdown |
| View balance history | Taps a peer | Sees all balances and settlements for that person |
| Link to transaction | Optionally links a balance to a bank transaction | Provides a cross-reference between the ledger entry and the bank record |
| Correct a wrong settlement | Taps "Add correction" on a balance with an incorrect settlement entry | A new settlement row is added with the correcting amount (positive or negative). The existing settlement is never edited — the ledger is append-only. The `remaining_amount` reflects all entries combined. |

---

## User Stories

- As a user, I want to log that Rahul owes me ₹1,500 from the dinner we split so I don't forget to follow up.
- As a user, I want to record when Rahul pays me back ₹1,000 so the remaining ₹500 stays tracked.
- As a user, I want to see who owes me money and how much, at a glance.
- As a user, I want to track that I owe my sister ₹3,000 from a shared hotel booking.
- As a user, I want to optionally link a peer settlement to the bank credit I received so I can reconcile my records.

---

## What It Does Not Do

- Does not automatically detect peer repayments from bank credits. The user logs all balances and settlements explicitly. (The `earnings` domain checks peer names as a heuristic, but the `peers` domain itself does not auto-process incoming credits.)
- Does not send payment reminders or notifications to peers. Peer contacts store names and optional phone numbers for display purposes only.
- Does not split expenses automatically from a group or shared purchase. Users log balances manually.
- Does not support settling a balance in a different currency than it was recorded in. If a balance is recorded in USD and the user enters a settlement in INR, the `remaining_amount` (denominated in USD) will not be reduced. The user must enter the settlement in the same currency as the balance, or manually convert the amount before entry.
- Does not integrate with UPI, WhatsApp, or any payment platform.

---

## Key Constraint

The peers ledger is append-only. Settlements are never edited — if the user made a mistake, they add a correcting entry rather than modifying an existing one. This preserves a complete audit trail of what actually happened and prevents ambiguity about real-world cash flows. When a settlement is entered incorrectly, the user adds a correcting entry rather than editing the existing one. There is no edit button on past settlements.
