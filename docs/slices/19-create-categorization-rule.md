# Slice: Create Categorization Rule

## User Goal
Set up an automatic rule so that future transactions matching a known merchant or description are categorised without AI or manual input.

## Trigger
User notices that "Swiggy" transactions keep being flagged as low-confidence by the AI, or wants to ensure all future Zomato debits go to "Food & Dining" automatically. User navigates to Settings → Categorization Rules → Add Rule.

## Preconditions
- User is authenticated.
- At least one active category exists to assign to.

## Steps

### Step 1: Define the Pattern
**User action**: Enters:
- Pattern text — e.g., "swiggy"
- Match type:
  - `contains`: matches if `raw_description` contains the pattern (case-insensitive)
  - `starts_with`: matches if description starts with the pattern
  - `exact`: matches if description exactly equals the pattern
  - `regex`: matches if description matches the regex (e.g., `^UPI/\d+/ZOMATO`)
- Category — selects from the active category list
- Priority — integer; higher numbers are checked first (default 0)

For regex match type, the UI validates the pattern is a valid regular expression before allowing submission.

### Step 2: Rule Created
**User action**: Taps "Save".
**System response**: A `categorization_rules` row is inserted (`is_active = true`). No event is published — rules take effect immediately on the next `suggest_category()` call.

### Step 3: Rule Applied Going Forward
**User action**: None.
**System response**: The next time `suggest_category()` is called (during statement processing or any future transaction):
1. The engine loads all active rules for this user, ordered by `priority DESC`.
2. If any rule matches `raw_description`, it returns `confidence=1.0, source='rule'` immediately — no AI call.
3. The workflow marks the row as `auto_classified` and does not pause for user input.

The rule also applies during bulk import (`ImportProcessingWorkflow`) — all rows that match a rule are categorised deterministically without the AI being consulted.

## Domains Involved
- **categorization**: Owns `categorization_rules` table; `suggest_category()` evaluates rules before AI.
- **statements** (downstream): Workflows call `suggest_category()` per row — rules short-circuit AI calls.
- **import_** (downstream): Bulk import uses rules for batch categorisation.

## Edge Cases & Failures
- **Overly broad pattern**: A rule with `contains: "NEFT"` would match almost every bank transfer, assigning them all to one category. The user should be specific. The UI could warn when a pattern is very short or generic.
- **Conflicting rules with same priority**: Both rules are checked in insertion order. The first match wins. Users should use `priority` to resolve conflicts explicitly.
- **Regex syntax error**: Rejected at validation. User must fix the regex before saving.
- **Rule matches a transaction that should be a transfer**: If a rule is set up for a merchant that occasionally appears as a self-transfer, the transfer detection step (Step 0 in `suggest_category()`) takes precedence — `type='transfer'` always returns "Self Transfer" regardless of any rules.

## Success Outcome
Future transactions matching the pattern are auto-classified with `confidence=1.0, source='rule'`, bypassing AI and never pausing for user input.
