# Slice: Manage Earning Sources

## User Goal
Create named income source labels (e.g., "Think41 Salary", "Freelance — Acme Corp") to organise and filter income by origin.

## Trigger
User navigates to Earnings → Sources, or is prompted to create a source when adding a manual earning.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Create an Earning Source
**User action**: Taps "Add source". Enters:
- Name — required (e.g., "Think41 Salary")
- Type — selects from: salary | freelance | rental | dividend | interest | business | other

**System response**: An `earning_sources` row is inserted (`is_active = true`). No event published. The source immediately appears in the earning source dropdown for future manual earnings and for the auto-classification heuristics.

### Step 2: Source Used in Heuristics
**User action**: None — applies automatically.
**System response**: When `TransactionCreated` fires for a credit, the earnings handler checks if the credit amount is ±5% of an `earning_sources` entry's historical credit amounts on a similar day of month. If a match is found with high confidence, the `earnings` record is auto-created and linked to this source.

### Step 3: Edit a Source
**User action**: Taps "Edit" on a source, changes name or type.
**System response**: `earning_sources` row updated. Existing `earnings` rows linked via `source_id` reflect the updated source name in the UI. Historical `source_type` values on individual `earnings` rows are not changed — they are snapshots.

### Step 4: Deactivate a Source
**User action**: Toggles a source to inactive.
**System response**: `is_active = false`. The source no longer appears in the manual earning dropdown. Existing `earnings` rows linked to this source remain intact. The `source_type` field on `earnings` rows allows aggregation to continue even for inactive or deleted sources.

## Domains Involved
- **earnings**: Owns `earning_sources` table.

## Edge Cases & Failures
- **Source deleted**: The `earnings.source_id` column allows NULL. Existing earnings linked to a deleted source retain `source_type` which preserves income aggregation. The `source_id` FK would be orphaned (no PG FK constraint on this column — the domain uses soft deletes and nullable source_id by design).
- **Two sources with the same name and type**: Allowed — the user may have two separate freelance clients and wants to track them as distinct sources.

## Success Outcome
Named income sources are available for selection when logging earnings, and appear as filter/grouping options in the earnings dashboard.
