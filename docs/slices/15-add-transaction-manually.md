# Slice: Add Transaction Manually

## User Goal
Log a transaction that does not appear in any statement or import (e.g., a cash payment, a UPI transfer not yet in a statement).

## Trigger
User taps the "+" / "Add transaction" button from the transaction list or home screen.

## Preconditions
- User is authenticated.
- At least one active account exists (to attribute the transaction to).

## Steps

### Step 1: Fill Transaction Details
**User action**: Enters:
- Account — selects from active `bank_accounts` / `credit_cards` (via `user_accounts_summary` view)
- Type: debit | credit | transfer
- Amount — required
- Currency — defaults to the account's primary currency
- Date — defaults to today
- Description — optional free text (stored as `raw_description`)
- Notes — optional

### Step 2: Select Category (via transaction items)
**User action**: Assigns at least one category:
- Simple case: selects a single category from the category list. One `transaction_items` row will be created with `amount = full transaction amount`, `label = NULL`, `is_primary = true`.
- Split case: taps "Split" and assigns multiple categories with amounts and optional labels (e.g., "Headphones ₹1200 → Shopping", "Olive oil ₹800 → Groceries").

**System response**: For transfer type: the "Self Transfer" category (kind='transfer') is automatically selected, bypassing the category picker.
For debit: only expense categories are shown.
For credit: only income categories are shown.

### Step 3: Submit
**User action**: Taps "Save".
**System response**:
1. Fingerprint is computed: `SHA-256(lower(trim(description)) + date.isoformat() + str(amount))`.
2. Uniqueness check: `UNIQUE(user_id, fingerprint)` — if a duplicate exists, the user is warned (they may be double-logging a transaction already in a statement).
3. `transactions` row inserted (`source = 'manual'`).
4. One or more `transaction_items` rows inserted.
5. `TransactionCreated` event published.
6. `TransactionCategorized` event published (with items payload for budgets).

### Step 4: Downstream Processing
**User action**: None.
**System response**:
- `earnings` domain processes `TransactionCreated`: if credit, applies heuristics to classify as income or peer repayment. May publish `EarningClassificationNeeded`.
- `investments` domain processes `TransactionCreated`: if debit, checks against active SIP registrations.
- `budgets` domain processes `TransactionCategorized`: updates `budget_progress` for matching goals and fires alerts if thresholds crossed.

## Domains Involved
- **transactions**: Creates the transaction and items, publishes events.
- **categorization**: Provides the category list for the picker (`categories_for_user` view).
- **earnings**: Classifies credit as income, peer repayment, or ambiguous.
- **investments**: Checks debit against SIP registrations.
- **budgets**: Updates spend tracking.

## Edge Cases & Failures
- **Duplicate fingerprint**: User is warned that a transaction with the same description, amount, and date already exists. They can proceed (creates a second transaction) or cancel.
- **Split items don't sum to total amount**: Form validation blocks submission.
- **Transfer without specifying destination account**: Transfer transactions are assigned the "Self Transfer" category but do not require a destination account field — Elixir does not track account balances, so a destination account reference is not needed.
- **Zero-amount transaction**: Rejected — amount must be > 0.

## Success Outcome
The transaction appears in the ledger with its category. Budget progress is updated and the earnings / SIP detection logic has processed it.
