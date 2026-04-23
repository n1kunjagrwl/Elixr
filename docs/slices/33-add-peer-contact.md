# Slice: Add Peer Contact

## User Goal
Add a friend, family member, or colleague to the peer contacts list so their shared expense balances can be tracked.

## Trigger
User navigates to Peers → Add Contact, or taps "Add new person" when logging a peer balance.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Enter Contact Details
**User action**: Enters:
- Name — required (e.g., "Rahul", "Mom")
- Phone number — optional (informational only; not used for notifications or messaging)
- Notes — optional (e.g., "College roommate", "Flatmate until March")

### Step 2: Contact Created
**User action**: Taps "Save".
**System response**: A `peer_contacts` row is inserted. No event is published — the peers domain has no event-driven behaviour.

The contact is immediately available:
- In the peer balance creation screen to select as the other party.
- In the `peer_contacts_public` view (id, user_id, name) used by the `earnings` domain to check incoming credits against known peer names (a ₹500 NEFT from "Rahul" may be a repayment, not income).

## Domains Involved
- **peers**: Owns `peer_contacts` table.
- **earnings** (downstream read): Uses `peer_contacts_public` view to heuristically classify credits during `TransactionCreated` processing.

## Edge Cases & Failures
- **Same name entered twice**: Allowed — a user might have two contacts named "Rahul". They are separate rows with distinct IDs and can be differentiated by phone or notes.
- **Phone number format**: Stored as free text — no validation or normalisation is applied. The phone is purely informational and never used by the system for sending messages.
- **Deleting a contact with open balances**: The service layer should warn the user that deleting a contact with open or partial `peer_balances` would orphan those records. The contact should be soft-deleted (or the UI should prevent hard deletion if balances exist).

## Success Outcome
The peer contact is available for logging shared expenses and settlements. The contact's name will also be used by the earnings heuristics to identify potential peer repayments.
