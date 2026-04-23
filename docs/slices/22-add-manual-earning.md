# Slice: Add Manual Earning

## User Goal
Log income that is not captured in any bank statement — e.g., a cash payment, a foreign wire transfer not yet imported, or a cheque received.

## Trigger
User taps "Add earning" from the Earnings screen.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Fill Earning Details
**User action**: Enters:
- Amount — required
- Currency — defaults to INR
- Date — defaults to today
- Source type — selects from: salary | freelance | rental | dividend | interest | business | other
- Earning source — optionally selects a named source from `earning_sources` (e.g., "Think41 Salary"). If no sources exist, this field is skipped.
- Source label — free text label used when no `source_id` is selected (e.g., "Consulting - Acme Corp")
- Notes — optional

### Step 2: Earning Saved
**User action**: Taps "Save".
**System response**: An `earnings` row is inserted with `transaction_id = NULL` (this is a manually-entered earning, not linked to a bank transaction). `source_type` is set from the selection. If an earning source was selected, `source_id` is linked. The `EarningRecorded` event is published via outbox.

### Step 3: Earning Visible in Dashboard
**User action**: None.
**System response**: The new earning appears in the earnings list and is included in income aggregations by `source_type` (e.g., "total freelance income this year"). The `source_type` column ensures this works even without a `source_id`.

## Domains Involved
- **earnings**: Owns `earnings` table, publishes `EarningRecorded`.

## Edge Cases & Failures
- **No earning source created yet**: User can still log the earning using `source_label` free text. Creating a named source is optional.
- **Same cash payment logged twice**: No fingerprint deduplication applies to manual earnings (no `raw_description` to hash). The user may inadvertently create a duplicate. The UI could warn if an earning with the same amount and date already exists, but does not block submission.
- **Foreign currency earning**: Amount and currency are stored as entered. The `fx` domain provides conversion rates for display purposes (e.g., showing USD earnings in INR equivalent on the dashboard).

## Success Outcome
The manually entered income appears in the earnings dashboard alongside auto-detected income from statements, contributing to income totals and source-type breakdowns.
