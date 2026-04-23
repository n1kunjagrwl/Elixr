# Slice: Record Peer Settlement

## User Goal
Log a partial or full payment that settles an outstanding peer balance — either money received from a peer or money paid to a peer.

## Trigger
User navigates to a peer's open balance and taps "Record settlement".

## Preconditions
- User is authenticated.
- A `peer_balances` row exists with `status = 'open'` or `'partial'` and `remaining_amount > 0`.

## Steps

### Step 1: Open the Balance
**User action**: Taps on an open peer balance.
**System response**: Balance detail shows:
- Description, original amount, settled amount so far, remaining amount
- Settlement history (all prior `peer_settlements` rows, ordered by `settled_at`)

### Step 2: Enter Settlement Details
**User action**: Enters:
- Amount — the amount being settled now (must be ≤ `remaining_amount`)
- Settlement method — cash | upi | bank_transfer | other (informational)
- Settled at — defaults to now (can be backdated)
- Linked transaction — optional (if this settlement arrived as a bank credit/debit, link the corresponding transaction)
- Notes — optional

### Step 3: Settlement Recorded
**User action**: Taps "Save".
**System response**: A `peer_settlements` row is inserted (append-only — settlements are never edited). `peer_balances.settled_amount` is incremented by the settlement amount. The `remaining_amount` generated column automatically updates:
- If `remaining_amount = 0` after this settlement: `peer_balances.status = 'settled'`
- If `remaining_amount > 0` and prior `settled_amount = 0`: `peer_balances.status = 'partial'`
- If `remaining_amount > 0` and prior `settled_amount > 0`: `peer_balances.status = 'partial'` (unchanged)

### Step 4: Correction If Mistake
**User action**: If the wrong amount was entered, the user taps "Add correction" rather than editing the existing settlement.
**System response**: A new `peer_settlements` row is inserted with a correcting amount (negative, or a note explaining the correction). Settlements are an append-only log — editing past entries is not supported. This preserves an accurate audit trail.

## Domains Involved
- **peers**: Owns `peer_balances`, `peer_settlements`; all status transitions handled here.

## Edge Cases & Failures
- **Settlement amount > remaining amount**: Rejected — settlement cannot exceed what is owed. User must enter an amount ≤ `remaining_amount`.
- **Settlement in a different currency than the balance**: The system stores the settlement in the entered currency. The remaining_amount is not automatically reduced (it's in the balance currency). The user should enter the INR-equivalent amount, or the UI should perform a currency conversion for display. This is a known limitation of the current simple ledger design.
- **User wants to reopen a settled balance** (e.g., the peer asks for the money back): Not directly supported. The user creates a new `peer_balances` entry representing the new amount owed. The prior settled balance remains in history.
- **Linking a bank credit to the settlement**: For `direction = 'owed_to_me'`, the settlement corresponds to a bank credit arriving from the peer. Setting `linked_transaction_id` on the `peer_settlements` row links the two records for reconciliation — but this does not trigger any automatic status change. The user must record the settlement explicitly.

## Success Outcome
The settlement is recorded in the append-only log. The balance `remaining_amount` is updated by PostgreSQL's generated column. If fully settled, the balance status is now "Settled" and removed from the active open-balances list.
