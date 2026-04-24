# Slice: View Earnings Dashboard

## User Goal
Open the Earnings screen and see total income for a chosen time period, broken down by source type, with auto-detected and manually entered earnings shown together.

## Trigger
User taps the "Earnings" tab in the app.

## Preconditions
- User is authenticated.
- At least one `earnings` row exists for this user (either auto-detected or manually entered).

## Steps

### Step 1: Load the Earnings Dashboard
**User action**: Navigates to the Earnings screen.
**System response**: The API queries all `earnings` rows for this user where `date` falls within the default time period (current calendar month). For each row, it retrieves `source_type`, `amount`, `currency`, `date`, `source_id`, `source_label`, and `transaction_id` (to distinguish auto-detected from manual).

### Step 2: View Monthly Total
**User action**: None — the screen renders.
**System response**: The top of the screen shows the total income for the selected period. If any earnings have a non-INR currency, the `fx` domain's `convert()` service method is called to express those amounts in INR for the aggregate total. The per-earning raw currency amounts are preserved for display in the detail rows.

### Step 3: View Breakdown by Source Type
**User action**: Scans the grouped breakdown.
**System response**: Earnings are grouped by `source_type` — `salary`, `freelance`, `rental`, `dividend`, `interest`, `business`, `other`. Each group shows:
- The group label (e.g., "Salary")
- The total for that source type across the period (non-INR converted to INR)
- The count of individual earnings records in the group
- A percentage share of total income

Groups with zero earnings in the selected period are hidden.

### Step 4: Distinguish Auto-Detected vs. Manual Earnings
**User action**: Views a source-type group.
**System response**: Within each group, individual earnings rows are displayed with a visual indicator:
- Rows where `transaction_id IS NOT NULL` were auto-detected from a bank statement credit and display a "Bank" badge.
- Rows where `transaction_id IS NULL` were manually entered and display a "Manual" badge.

Both types contribute equally to totals and breakdowns — the source of detection does not affect aggregation.

### Step 5: Select a Different Time Period
**User action**: Taps the period selector and picks one of: This Month, Last Month, This Quarter, Last Quarter, This Year, or a custom date range.
**System response**: The API re-queries `earnings` filtered by `date >= period_start AND date <= period_end` for the selected range. All aggregations (total, by-source-type grouping, auto-detected vs. manual counts) are recomputed and re-rendered for the new period.

### Step 6: Tap a Group to View Individual Earnings
**User action**: Taps a source-type group row (e.g., "Freelance").
**System response**: A detail list shows every `earnings` record in that group for the selected period, ordered by `date` descending. Each row shows:
- Date
- Amount (in its original currency) and the INR equivalent if non-INR
- Source label — either the linked `earning_sources.name` (if `source_id` is set) or the `source_label` free-text field (if `source_id` is NULL)
- Auto-detected / manual indicator
- Notes (if present)

### Step 7: Tap an Individual Earning
**User action**: Taps a specific earnings row in the detail list.
**System response**: The earnings detail screen opens, showing all fields for that record. From this screen the user can navigate to the linked bank transaction (if `transaction_id` is set) or tap "Edit" to modify the earnings record.

## Domains Involved
- **earnings**: Owns `earnings` and `earning_sources` tables; provides all income data.
- **fx**: Provides `convert()` for expressing non-INR earnings in INR for aggregated totals. Conversion uses the latest cached rate — display shows "rate as of {fetched_at}" when the rate is more than 24 hours old.

## Edge Cases & Failures
- **No earnings in the selected period**: The dashboard shows ₹0 total and an empty state message ("No income recorded for this period"). The period selector remains active so the user can navigate to a period where data exists.
- **All earnings are in INR**: The `fx` domain is not called; all amounts are used directly. No rate-staleness indicators appear.
- **FX rate unavailable for a non-INR currency**: If `fx.convert()` raises `FXRateUnavailableError`, the affected earning rows are shown in their original currency with a warning icon rather than an INR equivalent. The aggregate total is computed from the rows that could be converted; the missing rows are noted in a footer ("1 earning in USD excluded from total — rate unavailable").
- **Auto-detected earning later manually overridden**: If the user edited an auto-detected earnings record (changing its `source_type`), the record is bucketed by the stored `source_type` value, not the original inferred value. This is correct — the user's explicit correction takes precedence.
- **Source has been deleted**: If `source_id` points to an `earning_sources` row that the user later deactivated or deleted, the earnings row still displays using `source_label` (stored at creation time). The earning is not lost or unclassified.

## Success Outcome
The user sees a clear monthly income summary grouped by source type, with a visual distinction between auto-detected and manually entered earnings, and can navigate to any individual earning from the dashboard.
