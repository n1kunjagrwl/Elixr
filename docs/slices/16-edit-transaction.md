# Slice: Edit Transaction

## User Goal
Correct or update an existing transaction's category, notes, type, or item breakdown.

## Trigger
User taps on a transaction in the list and selects "Edit".

## Preconditions
- User is authenticated.
- The transaction (`transactions` row) exists and belongs to this user.

## Steps

### Step 1: Open Transaction Edit Form
**User action**: Taps a transaction → taps "Edit".
**System response**: Transaction details are loaded from `transactions` + `transaction_items`. The form is pre-filled with current values.

### Step 2: Edit Fields
**User action**: Changes one or more fields:
- **Notes**: Free text update.
- **Type**: Change debit ↔ credit ↔ transfer.
- **Category/Items**: Re-assign category, change split amounts, add or remove item labels.

### Step 3: Save Changes
**User action**: Taps "Save".
**System response**: The `transactions` row is updated (`updated_at` refreshed). `transaction_items` rows are replaced with the new items. A `TransactionUpdated` event is published via outbox with:
- `changed_fields`: list of what changed (e.g., `['items', 'notes']`)
- `old_items`: previous items snapshot (set only if `'items'` in `changed_fields`)
- `new_items`: new items snapshot
- `date`: transaction date (needed by the budgets handler for period lookup)

### Step 4: Budget Retroactive Correction
**User action**: None.
**System response**: The `budgets` domain consumes `TransactionUpdated`. If `'items'` is in `changed_fields`:
1. For old_items: decrement `budget_progress.current_spend` for all goals matching the old categories (floor at 0).
2. For new_items: increment `budget_progress.current_spend` for all goals matching the new categories.
3. Recheck thresholds — if the re-categorisation pushes a goal over 80% or 100%, alerts fire.

If only `notes` or `type` changed (not items), the budgets handler skips entirely.

### Step 5: Mark as Transfer
**User action**: Special case — user changes `type` to `transfer`.
**System response**: `TransactionUpdated` with `changed_fields = ['type']`. The `budgets` domain checks `type == 'transfer'` at the top of every handler and skips. The `earnings` domain similarly skips transfers. The "Self Transfer" category (kind='transfer') is automatically assigned to the transaction items.

## Domains Involved
- **transactions**: Updates records, publishes `TransactionUpdated`.
- **budgets**: Performs retroactive spend correction via `TransactionUpdated`.
- **categorization**: Provides updated category list for the picker.

## Edge Cases & Failures
- **Re-categorisation of a transaction from a prior budget period**: The `budgets` handler resolves the period for `event.date` and adjusts `budget_progress` for that past period. This is intentional — corrections apply retroactively.
- **Changing type from debit to credit**: If the transaction was previously counted in a debit-category budget, the old_items are subtracted. The new credit items may trigger earnings classification (the `earnings` domain does not currently listen to `TransactionUpdated` — manual earnings edits are handled by the user directly in the earnings UI if needed).
- **Editing a statement-imported transaction**: Allowed. `source` remains `'statement_import'` — the source field is not changed on edit.
- **Editing a recurring-detected transaction**: Allowed. The label (`source = 'recurring_detected'`) is preserved.
- **Items updated but amounts don't sum to total**: Form validation blocks submission.

## Success Outcome
The transaction reflects the corrected category/notes/type. Budget progress for the affected period is retroactively adjusted.
