# Slice: Edit Account Details

## User Goal
Update the display name, billing cycle day, credit limit, or other metadata on an existing account.

## Trigger
User taps on an account in the accounts list and selects "Edit".

## Preconditions
- User is authenticated.
- The account (`bank_accounts` or `credit_cards` row) exists and `is_active = true`.

## Steps

### Step 1: Open Edit Form
**User action**: Taps "Edit" on an account.
**System response**: Account details are fetched from `bank_accounts` or `credit_cards` via the `user_accounts_summary` view. The form is pre-filled with current values.

### Step 2: Modify Fields
**User action**: Changes one or more fields — e.g., renames nickname from "HDFC Savings" to "HDFC Joint", updates `billing_cycle_day` from 1 to 15, adds a credit limit.
**System response**: Form validates changes (e.g., `billing_cycle_day` ≤ 28).

### Step 3: Save Changes
**User action**: Taps "Save".
**System response**: The `bank_accounts` or `credit_cards` row is updated (`updated_at` refreshed). No event is published for edits — downstream domains are not affected by metadata changes (they hold the `account_id` reference, not the display fields). The `user_accounts_summary` view reflects the change immediately for all subsequent queries.

## Domains Involved
- **accounts**: Updates the `bank_accounts` or `credit_cards` row.
- **budgets** (indirect): If `billing_cycle_day` is changed on a credit card, future budget periods using `period_anchor_day` derived from this card will reflect the new value. Existing `budget_progress` rows are not retroactively adjusted.

## Edge Cases & Failures
- **Renaming to a name already used by another account**: Allowed — nicknames are not unique. The user is responsible for keeping their own labels distinct.
- **Changing currency**: Allowed. Existing transactions retain their original currency. New transactions against this account will use the updated currency as the default.
- **Changing bank_name or account_type**: Purely cosmetic — no downstream impact.
- **Changing billing_cycle_day mid-period**: The current active `budget_progress` period is not recalculated. The new anchor takes effect for the next budget period that starts after the change.

## Success Outcome
Account metadata is updated and reflected immediately across the app wherever the account name or details are displayed.
