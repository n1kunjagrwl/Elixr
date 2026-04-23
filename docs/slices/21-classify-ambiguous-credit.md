# Slice: Classify an Ambiguous Credit Transaction

## User Goal
Decide whether a credit transaction in the bank account is income (and of what type) or a peer repayment, so the ledger reflects it accurately.

## Trigger
The `earnings` domain processed a `TransactionCreated` event for a credit transaction, could not confidently classify it as income or peer repayment, and published `EarningClassificationNeeded`. The `notifications` domain created an in-app notification: "New credit to classify".

## Preconditions
- A credit transaction exists in the `transactions` table.
- An `EarningClassificationNeeded` event was published for this transaction.
- A notification exists with deep-link `/earnings/classify?transaction_id={id}`.

## Steps

### Step 1: Tap Notification
**User action**: Taps the "New credit to classify" notification.
**System response**: Deep-link opens the classification screen showing the transaction details:
- Date, amount, currency
- Raw description from the statement
- Why the system was uncertain (e.g., "We could not determine if this is income or a repayment")

### Step 2: Select Classification
**User action**: Chooses one of:
1. **Income** — selects the income type (salary | freelance | rental | dividend | interest | business | other) and optionally links it to an earning source.
2. **Peer repayment** — selects the peer contact the money came from (or creates a new one). This links the credit to the peers domain.
3. **Ignore** — marks the credit as neither income nor a peer repayment (e.g., a refund, a cashback).

### Step 3: Submit Classification
**User action**: Taps "Confirm".
**System response for Income**:
- An `earnings` row is created with `transaction_id` linked to this transaction, `source_type` set as selected, and `source_id` if an earning source was linked.
- `EarningRecorded` event is published.
- The notification is marked resolved (or the user is redirected back).

**System response for Peer repayment**:
- The credit is flagged as a peer repayment. No `earnings` row is created.
- Optionally, a `peer_balances` entry is linked to record the settlement (if the repayment relates to an existing balance).
- No earnings event published.

**System response for Ignore**:
- No `earnings` row created. The transaction remains in the ledger as a credit with its existing category. No further action.

## Domains Involved
- **earnings**: Published `EarningClassificationNeeded`, consumes user response to create/skip `earnings` record.
- **notifications**: Surfaced the notification; marks it as actioned.
- **peers** (optional): If classified as peer repayment, the user may link to a peer balance.

## Edge Cases & Failures
- **User dismisses the notification without classifying**: The transaction remains uncategorised for income purposes. The notification stays unread. The user can return to it any time via the notifications screen.
- **Same transaction classified as income twice**: The `earnings` handler checks for an existing `earnings` row with `transaction_id` before creating a new one (idempotency). A second "Income" classification is blocked or overwrites the first.
- **Amount is a common salary amount but description is ambiguous**: The system already ran heuristics (keyword check, amount ±5% match, peer name check). This notification was triggered because heuristics returned a split verdict. The user's explicit choice overrides all heuristics.
- **The credit is actually a bank interest credit**: User selects "Income → Interest". An `earnings` row is created with `source_type = 'interest'`.

## Success Outcome
The credit is correctly labelled as income, a peer repayment, or ignored. Income totals in the earnings dashboard reflect the classification. The notification is resolved.
