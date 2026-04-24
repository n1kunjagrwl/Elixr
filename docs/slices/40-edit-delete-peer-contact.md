# Slice: Edit or Delete Peer Contact

## User Goal
Update the name, phone number, or notes for a peer contact, or permanently remove a contact who is no longer relevant.

## Trigger
User navigates to the Peers screen, taps a contact, and selects "Edit" or "Delete".

## Preconditions
- User is authenticated.
- The `peer_contacts` row exists and belongs to this user.

## Steps

### Step 1: Open Contact Detail
**User action**: Taps a contact on the Peers screen.
**System response**: The contact detail screen displays:
- `name`, `phone` (if set), `notes` (if set)
- All `peer_balances` for this contact grouped by status: Open, Partial, Settled
- An "Edit" button and a "Delete" button

---

## Editing a Peer Contact

### Step 2a: Open Edit Form
**User action**: Taps "Edit".
**System response**: A form opens pre-filled with the contact's current `name`, `phone`, and `notes`.

### Step 3a: Make Changes
**User action**: Updates one or more fields:
- **Name** — required; used for display on all balance and settlement screens.
- **Phone** — optional; stored for the user's reference. Not used for notifications or any automated action.
- **Notes** — optional free text; any context the user wants to keep (e.g., "Roommate 2022–2024").

### Step 4a: Save Changes
**User action**: Taps "Save".
**System response**: The `peer_contacts` row is updated in place. `updated_at` is refreshed. No events are published — peer contact edits have no downstream domain reactions. The updated name is immediately reflected on all balance and settlement screens that reference this contact.

---

## Deleting a Peer Contact

### Step 2b: Attempt Delete
**User action**: Taps "Delete".
**System response**: Before proceeding, the system checks whether this contact has any `peer_balances` rows with `status = 'open'` or `status = 'partial'` (i.e., `remaining_amount > 0`).

### Step 3b — Path A: Open Balances Exist — Deletion Blocked
**User action**: None.
**System response**: A blocking message is shown:

> "This contact has {N} unsettled balance(s) totalling ₹{X}. Settle or remove these balances before deleting the contact."

The delete is rejected. The user must either:
1. Record settlements for all open/partial balances until `status = 'settled'` for each (slice 35), or
2. Manually delete the individual `peer_balances` rows (if a future "delete balance" feature exists) to clear the constraint.

No partial deletion occurs — if even one balance is open, the contact cannot be deleted.

### Step 3b — Path B: No Open Balances — Deletion Proceeds
**User action**: Confirms the deletion in a confirmation dialog ("Delete contact? This cannot be undone.").
**System response**: The `peer_contacts` row is hard-deleted from the database. All associated `peer_balances` rows (which are all `status = 'settled'`) and their `peer_settlements` rows are also deleted in cascade. The contact no longer appears anywhere in the Peers UI.

No events are published — no other domain reacts to peer contact deletion. The `peer_contacts_public` SQL view (consumed by the `earnings` domain for credit classification) will no longer return this contact's name, so future credits mentioning this contact's name will not be flagged as potential peer repayments.

## Domains Involved
- **peers**: Owns `peer_contacts`, `peer_balances`, `peer_settlements`; enforces the open-balance deletion guard; performs hard delete.

## Edge Cases & Failures
- **Contact has only settled balances**: Deletion is allowed. All settled `peer_balances` and their `peer_settlements` are hard-deleted in cascade alongside the contact. This is intentional — once settled, the history is the user's to keep or discard.
- **Contact has no balances at all**: Deletion is allowed immediately with no blocking check. A contact with no balance history is safe to delete.
- **Editing a contact name that appears in bank statement descriptions**: Changing the contact's name in Elixir has no effect on past bank statement descriptions. The `earnings` domain's credit classification heuristic queries `peer_contacts_public` at classification time — it will use the updated name for future credits but cannot retroactively reclassify past credits.
- **Concurrent settlement during delete attempt**: If another session settles the last open balance while the delete confirmation dialog is open, the re-check on confirmation will pass and the deletion succeeds. The guard is re-evaluated at the moment of the confirmed delete, not only at the time the dialog opens.
- **Phone number contains PII**: Phone numbers are never logged. The column is stored as plain text but excluded from all application logs per the no-PII logging policy.

## Success Outcome
**Edit**: The contact's name, phone, or notes are updated and immediately reflected throughout the app.

**Delete**: The contact and all their settled balance history are permanently removed. If open balances existed, the deletion was blocked with a clear message guiding the user to settle first.
