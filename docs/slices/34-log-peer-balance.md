# Slice: Log Peer Balance

## User Goal
Record that a peer owes the user money (or that the user owes a peer) arising from a shared expense, split bill, or informal loan.

## Trigger
User navigates to Peers → Add Balance, or taps "Log what they owe" on a peer's contact page.

## Preconditions
- User is authenticated.
- The peer contact exists in `peer_contacts`.

## Steps

### Step 1: Select Peer
**User action**: Selects the peer from the contact list, or searches by name.
**System response**: Peer's current open balances are shown for context (so the user can see existing records before adding a new one).

### Step 2: Enter Balance Details
**User action**: Enters:
- Description — required (e.g., "Goa trip accommodation", "Dinner at Smoke House Deli")
- Direction:
  - **Owed to me** — this peer owes the user money
  - **I owe** — the user owes this peer money
- Original amount — required
- Currency — defaults to INR
- Notes — optional
- Linked transaction — optional (if this balance originated from a known bank transaction, the user can link it by selecting from their transaction list; sets `peer_balances.linked_transaction_id`)

### Step 3: Balance Created
**User action**: Taps "Save".
**System response**: A `peer_balances` row is inserted:
- `status = 'open'`
- `settled_amount = 0`
- `remaining_amount` (PostgreSQL generated column) = `original_amount - settled_amount` = `original_amount`

No event is published. The balance appears in the peer's balance list under the user's account.

## Domains Involved
- **peers**: Owns `peer_contacts`, `peer_balances`.
- **transactions** (optional reference): `linked_transaction_id` can point to a `transactions` row, but no FK constraint — the link is informational.

## Edge Cases & Failures
- **Multiple balances with the same peer**: Fully supported — the user may have several open balances with the same person (dinner, trip, loan). Each is a separate row with its own description and amount.
- **Amount split unevenly** (e.g., the user paid ₹3000 for a dinner shared three ways; each person's share is ₹1000): The balance should reflect only the peer's share (₹1000), not the full ₹3000. The user is responsible for entering the correct net amount owed.
- **Logging the originating transaction**: The `linked_transaction_id` is optional. Many shared expenses are paid in cash and have no bank transaction. For expenses paid by card, the user can link the corresponding debit transaction for reconciliation.
- **Currency mismatch** (e.g., owed in USD but user's primary is INR): The balance is stored in the specified currency. FX conversion is handled by the user when settling — the settlement amount is entered in whatever currency the repayment actually happens in.

## Success Outcome
The balance is recorded and appears in the peer's balance summary with status "Open". The user can track total amount owed to/from this peer.
