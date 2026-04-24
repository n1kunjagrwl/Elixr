# Business Intent: notifications

## Why This Domain Exists

Elixir works largely in the background — statements are processed asynchronously, budgets are tracked passively, investments are valued on a schedule. Without a notification layer, the user would need to actively check each part of the app to find out what has happened since their last visit. The notifications domain surfaces those events as actionable banners so the user knows exactly what needs their attention when they open the app.

---

## What It Provides

- An **in-app notification feed** that collects all alerts and status updates from across the system in one place.
- **Actionable prompts** — notifications include a deep link that takes the user directly to the relevant screen (confirm a classification, review a budget, check a statement, etc.).
- **Unread tracking** — notifications are marked unread until the user explicitly reads them, with a count visible in the UI.
- **Notification history** — past notifications remain available so the user can review them even after marking them read.

---

## Events That Create Notifications

| Source | Trigger | What the user sees |
|---|---|---|
| Account added | User adds a bank account or credit card | "Upload a statement or log a transaction to start tracking {nickname}" |
| Statement processed | Statement extraction completes | "{n} transactions from {account} are ready to review" |
| Statement partially imported | Statement timed out before all rows classified | "Rows from {date} to {date} were discarded — re-upload to process them" |
| Budget 80% warning | Spending reaches 80% of a category limit | "You've used 82% of your Food & Dining budget this month" |
| Budget breached | Spending exceeds 100% of a category limit | "You've exceeded your Shopping budget by ₹1,200" |
| SIP detected | A debit matches a registered SIP | "₹5,000 debit looks like your Axis Midcap Fund SIP — tap to confirm" |
| Ambiguous credit | Earnings domain can't tell if a credit is income or a repayment | "A ₹45,000 credit arrived — is this income or a repayment? Tap to classify" |
| Import complete | CSV bulk import finishes | "{n} transactions imported. {m} duplicates skipped" |

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| View notifications | Opens notification feed | Sees all unread notifications first, then older ones |
| Act on a notification | Taps a budget alert | Navigates to the budget screen for the affected category |
| Mark as read | Taps "Mark read" on a single notification | `read_at` is set; notification moves to the read section |
| Mark all read | Taps "Mark all read" | All unread notifications are cleared |

---

## User Stories

- As a user, I want to be notified when my statement is done processing so I don't have to keep checking.
- As a user, I want a heads-up when I'm approaching my Food & Dining budget limit so I can adjust before going over.
- As a user, I want to know when a debit that looks like my SIP arrives so I can confirm it was processed correctly.
- As a user, I want to be asked about ambiguous credits as soon as they come in so my income figures stay accurate.
- As a user, I want all these alerts in one place so I don't miss anything important.

---

## What It Does Not Do

- Does not send SMS or push notifications. All notifications are in-app only at this stage.
- Does not originate events. Every notification is a reaction to something another domain already did.
- Does not support snooze, grouping, or priority tiers.
- Does not delete notifications — they are marked read and eventually hidden from the feed after 90 days, but never removed from the database.

---

## Key Constraint

The notifications domain has no business logic of its own. It is purely reactive: it receives events from other domains and converts them into user-facing messages. Adding a new notification type means subscribing to a new event — no business rules need to change in this domain.
