# Slice: Confirm SIP Detection

## User Goal
Respond to a system notification that a possible SIP payment was detected, confirming it is correct (or dismissing it) so the transaction is properly linked to the investment holding.

## Trigger
User taps a "SIP payment detected" push notification or in-app notification banner. The notification was created by the Notifications domain after the Investments domain published a `SIPDetected` event.

## Preconditions
- A `SIPDetected` event has been published for this user, meaning:
  - A debit transaction was created (via statement upload, CSV import, or manual entry).
  - The transaction matched an active `sip_registrations` row (amount within ±2%, date within ±3 days of `debit_day`, account matches).
- A `notifications` row of type `SIPDetected` exists for this user, unread, with `metadata` containing: `transaction_id`, `sip_registration_id`, `instrument_name`, `amount`.
- The `sip_registrations` row referenced in the notification is still `is_active = true`.

## Steps

### Step 1: View the Notification
**User action**: User taps the notification. Notification body reads: "We noticed a ₹{amount} debit that looks like your {instrument_name} SIP. Tap to confirm."

**System response**: App navigates to route `/investments/sip/confirm` with the `sip_registration_id` and `transaction_id` as query parameters. The confirmation screen is loaded.

### Step 2: Review the Match Details
**User action**: User reviews the confirmation screen, which shows:
- The transaction details: date, amount, account name, payee/description as parsed from the bank statement.
- The matched SIP: instrument name, registered amount, registered debit day, frequency.
- A match summary: "Debit of ₹{amount} on {date} from {account} — matched to your {instrument_name} SIP (₹{registered_amount}/month on the {debit_day}th)."

**System response**: Backend fetches the transaction and the SIP registration from the database and returns the comparison data. If either record has been deleted in the interim, the screen shows "This match is no longer valid" and the confirm/dismiss buttons are hidden.

### Step 3a: Confirm the Match
**User action**: User taps "Yes, this is my SIP".

**System response**:
1. Backend publishes a `SIPLinked` event with `transaction_id` and `sip_registration_id`.
2. The Investments domain handles `SIPLinked`:
   - The transaction is marked as linked to this SIP registration.
   - The `holdings` row for this instrument is optionally updated: if the user's units or cost basis has changed, a separate edit flow handles that (this slice only confirms the link, it does not auto-update holdings).
3. The notification's `read_at` timestamp is set to now.
4. A success toast is shown: "Linked! This ₹{amount} debit is now recorded as your {instrument_name} SIP payment."
5. The transaction's category in the Transactions domain may be updated to "Investment — SIP" if it was uncategorised.

### Step 3b: Dismiss the Match
**User action**: User taps "No, this isn't my SIP".

**System response**:
1. No `SIPLinked` event is published.
2. The notification's `read_at` timestamp is set to now.
3. The transaction remains unlinked to any SIP. It stays in the transaction list with its original category.
4. A toast is shown: "Dismissed. The transaction remains unlinked."
5. The SIP registration remains `is_active = true` — a missed detection does not deactivate the registration.

### Step 4: Handle Multiple Pending Notifications (if applicable)
**User action**: If the same transaction matched multiple SIP registrations, the user sees multiple "SIP payment detected" notifications — one per match. After acting on one, the others remain in the notification inbox.

**System response**: The user should confirm the correct match and dismiss the incorrect ones. Confirming one does not auto-dismiss the others; each must be acted on individually. If two notifications both get confirmed for the same transaction (edge case via rapid tapping), the backend deduplicates on `SIPLinked` processing: the second confirm is a no-op or returns a 409.

## Domains Involved
- **Investments**: Publishes `SIPDetected`, handles `SIPLinked` to finalise the transaction-to-SIP link.
- **Notifications**: Creates and holds the `SIPDetected` notification; marks it read on user action.
- **Transactions**: The debit transaction that triggered detection; may receive a category update on confirm.

## Edge Cases & Failures
- **Transaction deleted before user responds**: Confirmation screen shows "This match is no longer valid." Both confirm and dismiss are unavailable. The notification is marked read automatically.
- **SIP registration deactivated before user responds** (e.g. bank account was removed): Screen shows "This SIP registration is no longer active." Confirm is disabled; user can only dismiss.
- **User never responds**: The notification stays unread indefinitely (no auto-expiry for SIPDetected type). It appears in the unread count and notification inbox until acted on.
- **Network error on confirm**: Frontend retries. If `SIPLinked` was already published on the first attempt, the retry is idempotent — the backend checks whether the link already exists and returns success without re-publishing.
- **Wrong instrument selected at registration**: If the user realises the notification is for the wrong instrument entirely (not their SIP), they should dismiss, then edit the SIP registration to correct the instrument or amount.

## Success Outcome
The debit transaction is linked to the correct SIP registration and investment holding. The notification is marked read. The portfolio's transaction history for that instrument reflects the SIP payment.
