# Slice: Edit Earning

## User Goal
Correct or update an existing earnings record — whether it was auto-detected from a bank statement or manually entered — by changing its source type, linked source, amount, currency, date, or notes.

## Trigger
User taps an individual earnings record and selects "Edit".

## Preconditions
- User is authenticated.
- The `earnings` row exists and belongs to this user.

## Steps

### Step 1: Open Earning Edit Form
**User action**: Taps an earnings record → taps "Edit".
**System response**: The edit form is pre-filled with the current values from the `earnings` row:
- `source_type` (dropdown: salary / freelance / rental / dividend / interest / business / other)
- `source_id` (optional — linked earning source from `earning_sources`)
- `source_label` (free-text label, shown and editable when `source_id` is NULL)
- `amount`
- `currency`
- `date`
- `notes`

For auto-detected earnings (`transaction_id IS NOT NULL`), the form also displays a read-only link to the originating transaction, shown as "Linked to bank transaction on {date}". This link cannot be removed via the edit form; the record's connection to its source transaction is informational and preserved.

### Step 2: Edit Fields
**User action**: Changes one or more fields.

Notable field behaviours:
- **source_type**: Changing this field categorises the earning differently going forward. Aggregations on the Earnings dashboard (slice 38) and filtered views (slice 45) group by the stored `source_type` value — so after saving, this earning will appear in the new group, not the old one. Historical `source_type` values are not tracked in a change log; the column stores the current best-known classification.
- **source_id**: User may switch from one named earning source to another, or clear the link entirely (setting `source_id` to NULL). When `source_id` is cleared, the `source_label` field becomes active for free-text entry.
- **amount and currency**: Editable. No re-deduplication or re-fingerprinting occurs on amount changes — the earning record is not a transaction and has no fingerprint.
- **date**: Editable. Changing the date moves the earning into a different monthly/quarterly grouping on the dashboard.
- **notes**: Free text, always editable.

### Step 3: Save Changes
**User action**: Taps "Save".
**System response**: The `earnings` row is updated in place. `updated_at` is refreshed. No event is published — editing an earning does not trigger re-classification, budget recalculation, or any downstream domain reaction.

The `source_type` stored on the row is a snapshot: it captures the user's current best classification of this earning. If the user had previously been auto-classified as `salary` and now changes it to `freelance`, the row stores `freelance` going forward. Prior monthly totals that included this earning as `salary` are not retroactively corrected — aggregations are always computed dynamically over the stored `source_type` values at query time, so they reflect the latest state automatically.

### Step 4: Earning Visible with Updated Values
**User action**: Returns to the Earnings dashboard or filtered list.
**System response**: The updated earning appears in its new grouping immediately. If `source_type` was changed, it no longer appears in the old group — it appears in the new group for the same period. Monthly and period totals are recomputed on next load.

## Domains Involved
- **earnings**: Owns the `earnings` table; performs the update; no event published.

## Edge Cases & Failures
- **Changing source_type on an auto-detected earning**: Allowed. The `transaction_id` link to the originating bank transaction is preserved; only the income classification changes. This is the primary correction path when the heuristic auto-classification was wrong (e.g., a peer repayment that was incorrectly classified as freelance income).
- **Clearing source_id with no source_label provided**: Form validation requires that at least one of `source_id` or `source_label` is filled. If the user clears `source_id`, they must enter a `source_label` before saving.
- **Changing amount on an auto-detected earning**: The `earnings.amount` is stored independently from the linked `transactions.amount`. Editing the earning's amount does not change the original bank transaction. This allows the user to record the net income amount (e.g., after tax withheld at source) separately from the gross credited amount in the transaction.
- **Saving with no changes**: A save with identical values updates `updated_at` but produces no visible change. This is harmless.
- **Concurrent edit**: If the `earnings` row was modified by a background process between the time the edit form loaded and the user saves, the last write wins (no optimistic locking). Given that only one user edits their own earnings, this is not a practical concern.

## Success Outcome
The earnings record reflects the user's correction. The Earnings dashboard and all filtered views immediately show the record under its updated groupings, with no stale data.
