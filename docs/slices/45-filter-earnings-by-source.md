# Slice: Filter Earnings by Source

## User Goal
Narrow the earnings list to a specific income type or named earning source, and view combined totals for that subset — for example, "show me all salary income this year" or "show me every payment from Acme Corp since January".

## Trigger
User is on the Earnings screen and opens the filter panel, or taps directly on a source-type group in the dashboard breakdown.

## Preconditions
- User is authenticated.
- At least one `earnings` row exists for this user.

## Steps

### Step 1: Open the Filter Panel
**User action**: Taps the filter icon on the Earnings screen.
**System response**: The filter panel opens with three independent filter dimensions:
- **Source type** — multi-select list of the possible `source_type` values: Salary, Freelance, Rental, Dividend, Interest, Business Income, Other
- **Earning source** — searchable dropdown of the user's named `earning_sources` (active entries only, `is_active = true`). Each item shows the source name and its type in parentheses, e.g., "Think41 Salary (Salary)".
- **Date range** — presets (This Month, Last Month, This Quarter, Last Quarter, This Year, Last Year) or custom start/end date.

All three dimensions default to "no filter" (all values included).

### Step 2: Filter by Source Type
**User action**: Selects one or more source types from the list (e.g., "Salary" only).
**System response**: The earnings query adds `WHERE source_type IN (:selected_types)`. The result includes all earnings of those types regardless of whether they have a `source_id` or only a `source_label`. Both auto-detected and manually entered earnings of the selected types are included.

The header total and grouped breakdown update to reflect only the filtered subset. For example, filtering to "Freelance" shows only freelance earnings, and the total at the top represents total freelance income for the selected period.

### Step 3: Filter by Named Earning Source
**User action**: Selects a specific earning source from the dropdown (e.g., "Acme Corp").
**System response**: The earnings query adds `WHERE source_id = :selected_source_id`. This returns all earnings linked to that specific named source across all `source_type` values. (It is technically possible for multiple `source_type` values to reference the same `source_id`, though this would be unusual — the filter returns all of them.)

Source type and earning source filters are combinable. Applying both narrows the results to earnings that match both the selected source type(s) AND the selected `source_id`.

### Step 4: Handle Earnings Without a source_id
**User action**: Views the filtered results after applying a named source filter.
**System response**: Only earnings with a matching `source_id` are shown. Earnings where `source_id IS NULL` are excluded when a source filter is active — these earnings have only a `source_label` free-text label and are not associated with any named source.

For earnings with `source_id IS NULL` that appear in an unfiltered view, the display label is taken from `source_label`. If `source_label` is also NULL (which should not occur in well-formed data), the row displays "Unlabelled" as a fallback.

### Step 5: Apply a Date Range Filter
**User action**: Selects "This Year" or enters a custom date range.
**System response**: The query adds `WHERE date >= :start_date AND date <= :end_date`. Date range combines with any active source type and earning source filters. The page resets to page 1 of results.

### Step 6: View Combined Totals
**User action**: Reviews the filtered results.
**System response**: The filtered list is headed by a summary section showing:
- **Total for this filter** — sum of all `earnings.amount` values matching the active filters, converted to INR where needed via `fx.convert()`. Non-INR earnings display both the original amount and the INR equivalent.
- **Count** — number of individual earnings records in the filtered set.
- **Breakdown** — if multiple `source_type` values are present in the filtered results (e.g., the user filtered by a specific source that has entries under both "Freelance" and "Business Income"), the breakdown shows sub-totals per source type.

Both auto-detected earnings (`transaction_id IS NOT NULL`) and manually entered earnings (`transaction_id IS NULL`) are counted together in totals — the filter does not distinguish between them unless a separate "Origin" filter is applied.

### Step 7: Filter to "Show Only Freelance This Year" (Combined Example)
**User action**: Selects source type = "Freelance" and date range = "This Year".
**System response**: The query becomes:
```
WHERE user_id = :uid
  AND source_type = 'freelance'
  AND date >= '2026-01-01'
  AND date <= '2026-12-31'
ORDER BY date DESC
```
The summary shows total freelance income year-to-date. All `source_label` values are shown for each row — entries with a named `source_id` show the source name; entries with only a `source_label` show that free text.

### Step 8: Clear Filters
**User action**: Taps "Clear filters" or taps the X on individual filter chips.
**System response**: The cleared filters are removed and the earnings list reverts to the full unfiltered view (all source types, all named sources, all dates) within the currently selected dashboard time period. Other active filters remain if only one was cleared.

## Domains Involved
- **earnings**: Owns `earnings` and `earning_sources`; provides all filtered data; no cross-domain reads required for the filter query itself.
- **fx**: Provides `convert()` for expressing non-INR earnings in INR for the combined totals summary. The same staleness behaviour applies as in slice 38 — if a rate is more than 24 hours old, a "rate as of {fetched_at}" note is shown.

## Edge Cases & Failures
- **Earning source filter and source_id is NULL on some rows**: As noted in Step 4, these rows are excluded from the named source filter. If the user is looking for "all income from Acme Corp" but some payments were entered with only a `source_label = "Acme Corp"` (free text) rather than a linked `source_id`, those entries will not be found by the source filter. The user would need to search by keyword in the transaction search (slice 44) or scroll the unfiltered earnings list. This is a known limitation of the two-path labelling design.
- **No earnings match the combined filters**: An empty state is shown ("No earnings match these filters for the selected period"). All filter chips remain active and visible so the user can remove one to widen the search.
- **Earning source has been deactivated**: Deactivated sources (`is_active = false`) are hidden from the source filter dropdown for new entries, but existing `earnings` rows that reference a deactivated `source_id` are still returned in filter results. The source name is shown with a "(Inactive)" tag to indicate the source is no longer in use.
- **All filtered earnings are in non-INR currencies and no FX rate is available**: If `fx.convert()` raises `FXRateUnavailableError` for every row in the filtered set, the total is shown as "Total unavailable — FX rates missing" rather than a number. Individual earnings rows are still displayed in their original currencies.
- **Large filtered result set**: Pagination applies to the earnings list. The summary totals (count and amount) are computed over the full filtered result set server-side (a single aggregate query), while the list view paginates. This means the total shown in the header is always accurate even before all pages are loaded.
- **source_label is NULL on a row with no source_id**: This should not occur in well-formed data (the service layer should require at least one of the two to be set). If encountered, the UI shows "Unlabelled" for that row's source display.

## Success Outcome
The user can confidently answer questions like "how much did I earn from freelancing this year?" or "what has Acme Corp paid me since January?" by applying a combination of source type, named source, and date range filters. Combined totals are shown prominently at the top of the filtered view, with all amounts expressed in INR where applicable.
