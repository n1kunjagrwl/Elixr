# Slice: Browse and Search Transactions

## User Goal
Find and review specific transactions by scrolling the full transaction history, filtering by account, category, date range, type, or source, and searching by keyword within transaction descriptions.

## Trigger
User taps the "Transactions" tab in the app.

## Preconditions
- User is authenticated.
- At least one `transactions` row exists for this user.

## Steps

### Step 1: Load Default Transaction List
**User action**: Navigates to the Transactions screen.
**System response**: The API queries `transactions` for this user, ordered by `date DESC`, then `created_at DESC` (to resolve ties within the same date). The default view shows the first page of results with no active filters. Each row in the response includes:
- `id`, `date`, `amount`, `currency`, `type`, `source`
- `raw_description` (the original statement description or user-entered description)
- `notes` (if set)
- Account name and kind — resolved by joining against the `user_accounts_summary` view (Pattern 1, cross-domain read)
- Primary category — the `transaction_items` row where `is_primary = true`, joined with category name and icon from the `categories_for_user` view (Pattern 1, cross-domain read)

The account name is resolved from `user_accounts_summary` rather than querying `bank_accounts` or `credit_cards` directly, in accordance with the cross-domain view read pattern.

### Step 2: Paginate Through Results
**User action**: Scrolls to the bottom of the list or taps "Load more".
**System response**: The API returns the next page of results using cursor-based pagination (keyed on `(date, id)` to avoid gaps when new transactions arrive). The page size is fixed (e.g., 50 rows). Pagination state is maintained client-side.

### Step 3: Filter by Account
**User action**: Opens the filter panel and selects one or more accounts from the account picker.
**System response**: The account picker is populated by querying `user_accounts_summary` filtered by `user_id` and `is_active = true`. The list shows both bank accounts and credit cards with their nicknames and `last4`.

On applying the filter, the transaction query adds `WHERE account_id IN (:selected_ids) AND account_kind IN (:selected_kinds)`. The page resets to the first page.

### Step 4: Filter by Category
**User action**: Opens the filter panel and selects one or more categories from the category picker.
**System response**: The category picker is populated by querying `categories_for_user` (the SQL view exposed by the `categorization` domain) filtered with `WHERE user_id = :uid OR user_id IS NULL` to include both default and user-created categories. Only active categories (`is_active = true`) are shown.

On applying the filter, the query joins `transaction_items` and adds `WHERE ti.category_id IN (:selected_category_ids)`. Transactions with a split across multiple categories appear once if any of their items matches the selected categories. The page resets to the first page.

### Step 5: Filter by Date Range
**User action**: Opens the filter panel and selects a preset (Today, This Week, This Month, Last Month, This Year, Last Year) or enters a custom start and end date.
**System response**: The query adds `WHERE date >= :start_date AND date <= :end_date`. All other active filters are preserved and combined. The page resets to the first page.

### Step 6: Filter by Transaction Type
**User action**: Opens the filter panel and selects one or more of: Debit, Credit, Transfer.
**System response**: The query adds `WHERE type IN (:selected_types)`. Useful for viewing only expenses (debit) or only income (credit) without other filters. The page resets to the first page.

### Step 7: Filter by Source
**User action**: Opens the filter panel and selects one or more of: Manual, Statement Import, Bulk Import, Recurring Detected.
**System response**: The source values map directly to the `transactions.source` column:
- "Manual" → `source = 'manual'`
- "Statement Import" → `source = 'statement_import'`
- "Bulk Import" → `source = 'bulk_import'`
- "Recurring Detected" → `source = 'recurring_detected'`

The query adds `WHERE source IN (:selected_sources)`. The page resets to the first page. This filter is useful for auditing ("show me only manually entered transactions") or reviewing import results.

### Step 8: Keyword Search
**User action**: Types a search term into the search field (e.g., "Swiggy", "Netflix", "rent").
**System response**: The query adds `WHERE lower(raw_description) LIKE '%' || lower(:keyword) || '%'`. Search is performed against `raw_description` only — not against `notes`, category names, or item labels — because `raw_description` is the stable, original text from the statement and is consistent across all transaction sources. A full-text index on `raw_description` (or a `pg_trgm` index for LIKE performance) makes this efficient for large transaction histories.

Search is combinable with all other active filters — a user can filter to "Debit + This Month" and search "Swiggy" simultaneously.

The page resets to the first page on each search term change (debounced input, minimum 2 characters before triggering).

### Step 9: Clear Filters
**User action**: Taps "Clear filters" or removes individual filter chips.
**System response**: The affected filters are removed and the query reverts to the default state for those dimensions. Other active filters remain. The list reloads from page 1.

### Step 10: Tap a Transaction
**User action**: Taps a row in the list.
**System response**: The transaction detail screen opens, showing:
- Full `raw_description`, `date`, `amount`, `currency`, `type`, `source`
- Account name and kind (from `user_accounts_summary`)
- All `transaction_items` with category name, item `label`, and `amount` for each
- `notes` (if set)
- An "Edit" button (leads to slice 16)
- For `source = 'recurring_detected'`: a "Recurring" badge with the detected pattern
- For `source = 'bulk_import'` or `source = 'statement_import'`: a source badge
- If `transaction_id` is linked to a `peer_settlements` row: a "Linked to peer settlement" indicator (informational)

## Domains Involved
- **transactions**: Owns the `transactions` and `transaction_items` tables; provides all transaction data.
- **accounts**: Provides `user_accounts_summary` view for resolving account nicknames and `last4` without querying `bank_accounts` / `credit_cards` directly.
- **categorization**: Provides `categories_for_user` view for populating the category filter picker and resolving category names and icons for display.

## Edge Cases & Failures
- **Transaction with no items (un-categorised)**: Can occur if a transaction was created before categorisation completed. The row is still shown in the list with "Uncategorised" as the category display. It appears in the list for all filters except category-specific filters (which require a matching `transaction_items` row).
- **Keyword search returns too many results**: The LIKE search is unbounded by default. Very short or common search terms (e.g., "a") may return a large result set. The UI should enforce a minimum of 2 characters and may offer a result count cap ("showing first 200 of 1,432 results").
- **Multiple items in different categories on a split transaction**: When filtering by category C, a split transaction (e.g., Amazon order with both Shopping and Groceries items) appears in the list if either item matches C. In the list view, only the primary item (`is_primary = true`) is shown as the category badge. The detail view shows all items.
- **Account deactivated since transactions were created**: Transactions whose `account_id` references a deactivated account are still shown in the list. The `user_accounts_summary` view includes `is_active` — the UI can show "Deactivated account" as the account name for these rows rather than hiding the transactions.
- **Combining incompatible filters**: If the user filters by `type = credit` and `category = Food & Dining` (an expense category), no results will be found — credits are not categorised as expense categories. No error is raised; an empty state is shown.
- **Large date ranges**: Querying "This Year" on an account with thousands of transactions is handled by the server-side cursor pagination. The first page returns instantly; subsequent pages load on demand.

## Success Outcome
The user can quickly locate any transaction using any combination of account, category, date, type, source, and keyword filters. The list loads efficiently and the pagination keeps the experience responsive even for large transaction histories.
