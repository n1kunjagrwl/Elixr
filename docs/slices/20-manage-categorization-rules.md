# Slice: Manage Categorization Rules

## User Goal
Review, re-prioritise, edit, or disable existing categorization rules as transaction patterns evolve.

## Trigger
User navigates to Settings → Categorization Rules.

## Preconditions
- User is authenticated.
- At least one `categorization_rules` row exists for this user.

## Steps

### Step 1: View Rules List
**User action**: Opens the rules screen.
**System response**: All `categorization_rules` for this user are fetched (`is_active = true` first, then inactive). Displayed as a list showing: pattern, match type, target category, priority, and active/inactive status.

### Step 2A: Edit a Rule
**User action**: Taps "Edit" on a rule.
**System response**: Rule form pre-filled with current values. User can change pattern, match type, category, or priority. On save, the `categorization_rules` row is updated (`updated_at` refreshed). The change takes effect on the next `suggest_category()` call — no retroactive re-classification of existing transactions.

### Step 2B: Change Priority
**User action**: Changes the `priority` integer on one or more rules to control evaluation order.
**System response**: Higher `priority` values are evaluated first. If two rules both match a transaction, the higher-priority one wins. Priority is a simple integer — there is no drag-to-reorder UI requirement; the user enters numbers directly.

### Step 2C: Deactivate a Rule
**User action**: Toggles the rule to inactive.
**System response**: `is_active = false` is set. The rule is no longer evaluated by `suggest_category()`. Existing transactions classified by this rule are not changed — only future transactions are affected. The rule remains visible in the "inactive" section and can be re-activated.

### Step 2D: Delete a Rule
**User action**: Taps delete and confirms.
**System response**: The `categorization_rules` row is hard-deleted. No event published. Existing transactions are unaffected.

## Domains Involved
- **categorization**: Owns `categorization_rules` table; changes take effect immediately.

## Edge Cases & Failures
- **Re-activating a deactivated rule after bulk imports**: Previously imported transactions that were categorised as "Others" (because the rule didn't exist then) are not retroactively re-classified. The user would need to manually edit those transactions or re-import the data.
- **Setting priority to a very high number**: Fine — it just means this rule is always checked first. No ceiling on priority.
- **Two rules have the same priority**: They are evaluated in an unspecified order (insertion order in the DB query). The user should assign distinct priorities if ordering matters.

## Success Outcome
Rules are in the desired state (correct patterns, correct priorities, active/inactive as needed). Future statement and import processing reflects the updated rules immediately.
