# Slice: Browse Categories

## User Goal
View all available categories — both system defaults and personal custom categories — to understand what's available before categorising transactions or creating rules.

## Trigger
User navigates to Settings → Categories, or opens the category picker during transaction classification.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Open Category List
**User action**: Navigates to the categories screen.
**System response**: The API queries the `categories_for_user` view:
```sql
WHERE (user_id = :uid OR user_id IS NULL) AND is_active = true
```
This returns both system default categories (`user_id IS NULL`) and the user's custom categories (`user_id = :uid`). A plain `WHERE user_id = :uid` would return only custom categories — new users would see an empty list.

### Step 2: View Organised by Kind
**User action**: None — the list is rendered on arrival.
**System response**: Categories are grouped by `kind`:
- **Expense** (default + custom): Food & Dining, Groceries, Transport, Utilities, Shopping, Health & Medical, Entertainment, Travel, Education, Personal Care, Subscriptions, EMI & Loans, Rent, Investments (outflow), Others — plus any user-created expense categories.
- **Income** (default + custom): Salary, Freelance, Rental Income, Dividends, Interest, Business Income — plus any user-created income categories.
- **Transfer**: Self Transfer (system only).

Each category shows its icon, name, and whether it is a system default or user-created.

### Step 3: Toggle Inactive Categories
**User action**: Taps "Show inactive categories".
**System response**: Re-queries with `is_active = true` filter removed, showing all categories including those the user has hidden.

## Domains Involved
- **categorization**: Owns the `categories` table and `categories_for_user` view.

## Edge Cases & Failures
- **New user with no custom categories**: The view correctly returns only system defaults (15 expense + 6 income + 1 transfer = 22 categories). No empty state.
- **User has hidden a default category**: `is_active = false` was set for that category row (only possible for user-created categories; system defaults cannot be deactivated by users directly unless an admin operation is used).

## Success Outcome
User sees the complete list of categories they can use for transactions and rules, clearly organised by type.
