# Slice: Deactivate (Soft-Delete) Account

## User Goal
Remove an account from active use while preserving all historical transactions and statements linked to it.

## Trigger
User taps on an account and selects "Remove account".

## Preconditions
- User is authenticated.
- The account exists and `is_active = true`.

## Steps

### Step 1: Tap Remove Account
**User action**: Selects "Remove account" from the account's options menu.
**System response**: The system checks whether the account has any linked transactions (`transactions` where `account_id = this account`) or statement uploads (`statement_uploads` where `account_id = this account`).

### Step 2A: Account Has Linked History (Soft Delete)
**User action**: Confirms the removal in the confirmation dialog ("This account has transactions. It will be hidden but your history will be preserved.").
**System response**: `is_active = false` is set on the `bank_accounts` or `credit_cards` row. The `AccountRemoved` event is published via outbox. The account disappears from all active UI lists (new transaction dropdowns, statement upload selectors) but its `account_id` remains valid in all historical records.

### Step 2B: Account Has No History (Hard Delete Eligible)
**User action**: Confirms the removal.
**System response**: The service layer verifies zero linked transactions. The `bank_accounts` or `credit_cards` row is hard-deleted. `AccountRemoved` is published.

### Step 3: SIP Registrations Deactivated
**User action**: None.
**System response**: The `investments` domain consumes `AccountRemoved`. For all `sip_registrations` where `bank_account_id = event.account_id AND is_active = true`, `is_active` is set to `false`. This prevents false-positive SIP detection alerts from firing against an account the user considers removed.

## Domains Involved
- **accounts**: Owns the soft/hard delete logic, publishes `AccountRemoved`.
- **investments**: Consumes `AccountRemoved`, deactivates linked SIP registrations.

## Edge Cases & Failures
- **Account has open statement processing jobs**: Statement processing is in progress (e.g., `extraction_jobs.status = 'classifying'`). The system should warn the user and advise waiting for the job to complete before removing the account. Alternatively, the deactivation can proceed — in-progress workflows hold the `account_id` in their state and will continue to completion regardless of `is_active`.
- **Reactivating a soft-deleted account**: User navigates to "Inactive accounts" and restores it. `is_active = true` is set. No event is published for reactivation. SIP registrations are NOT automatically re-activated; the user must manually re-enable them.
- **Attempting to hard-delete an account with transactions**: Service layer rejects the request and returns an error explaining that the account has transaction history and can only be deactivated (soft-deleted).

## Success Outcome
The account is hidden from all active UI. Historical data (transactions, statements) is fully preserved. Any SIP detection for this account is disabled.
