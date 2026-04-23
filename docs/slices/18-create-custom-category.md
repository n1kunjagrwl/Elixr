# Slice: Create Custom Category

## User Goal
Add a personalised category not in the default list (e.g., "Pet Care", "Side Hustle Income").

## Trigger
User taps "Add category" from the categories screen, or taps "Create new category" from a transaction's category picker when no suitable default exists.

## Preconditions
- User is authenticated.

## Steps

### Step 1: Fill Category Details
**User action**: Enters:
- Name — required (e.g., "Pet Care")
- Kind — expense | income (transfer kind is reserved for the system's "Self Transfer" category)
- Icon — selects from an emoji/icon picker (optional)
- Parent category — optional, reserved for sub-categories (future use; `parent_id` column exists)

### Step 2: Category Created
**User action**: Taps "Save".
**System response**: A `categories` row is inserted with `user_id = current user`, `is_default = false`, `is_active = true`. A `slug` is generated from the name (e.g., "pet-care"). The `CategoryCreated` event is published via outbox.
The new category is immediately available in:
- The category picker for transactions and statement classification.
- The category selector for budget goals.
- The `suggest_category()` ADK call context — the user's custom categories are included in the prompt so the AI can suggest them for future transactions.

### Step 3: Category Available
**User action**: None.
**System response**: The `categories_for_user` view now includes the new row. No migration or cache invalidation needed — the view is live.

## Domains Involved
- **categorization**: Owns the `categories` table, publishes `CategoryCreated`.

## Edge Cases & Failures
- **Name duplicates an existing default**: Allowed — a user can create a custom "Food & Dining" (perhaps with a different icon). They are separate rows; the custom one has `user_id` set.
- **Name duplicates an existing custom category**: The system does not enforce uniqueness — the user may have two custom categories with the same name (different slugs if the name matches exactly). This is user error; the UI should warn but not block.
- **Creating a transfer-kind category**: The API rejects `kind = 'transfer'` for user-created categories. Transfer is a reserved kind managed by the system ("Self Transfer" is the only transfer category).

## Success Outcome
The new category appears in the user's category list and is immediately usable for transaction classification, rules, and budget goals.
