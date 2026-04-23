# Slice: Add Bank Account

## User Goal
Register a bank account label so transactions and statements can be attributed to it.

## Trigger
User taps "Add account" → selects "Bank account" from the accounts screen.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Fill Account Details
**User action**: Enters:
- Nickname (e.g., "HDFC Savings") — required
- Bank name (e.g., "HDFC Bank") — required
- Account type: savings | current | salary | nre | nro — required
- Last 4 digits of account number — optional, display only
- Primary currency — defaults to INR
**System response**: Form validates that nickname and bank_name are non-empty.

### Step 2: Account Created
**User action**: Taps "Save".
**System response**: A `bank_accounts` row is inserted (`is_active = true`). The full account number is never stored — only `last4` is kept. The `AccountLinked` event is published via outbox.

### Step 3: Onboarding Nudge
**User action**: None.
**System response**: The `notifications` domain consumes `AccountLinked` and creates an in-app notification:
- Title: "Account added"
- Body: "Upload a statement or log a transaction to start tracking {nickname}."
- Deep-link: `/statements/upload?account_id={id}`

The account appears in the account list and is immediately available as a source for statement uploads and manual transactions.

## Domains Involved
- **accounts**: Owns `bank_accounts` table, publishes `AccountLinked`.
- **notifications**: Consumes `AccountLinked`, creates onboarding nudge.

## Edge Cases & Failures
- **Duplicate nickname**: The system does not enforce unique nicknames — a user can have two accounts with the same label (e.g., two savings accounts). They are differentiated by `last4` in the UI.
- **NRE/NRO account type**: Stored as-is. The system does not apply any special business rules for non-resident accounts at this stage.
- **Currency other than INR**: The account is created with the specified currency. The `fx` domain will include this currency in its periodic rate refresh so transactions in this currency can be converted.

## Success Outcome
The bank account appears in the user's account list. The user can now upload a statement or log transactions against this account.
