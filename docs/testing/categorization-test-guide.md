# categorization — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The categorization domain turns raw bank statement descriptions — machine-readable strings like "UPI/123456/ZOMATOORD" — into meaningful labels such as "Food & Dining" or "Salary" that users actually recognise. It ships 22 sensible default categories for Indian users so no setup is required, and it lets users extend that taxonomy with custom categories and teach the system to recognise known merchants automatically via pattern rules. The `suggest_category()` service is the core engine: it checks user-defined rules first (deterministic, zero cost), falls back to a Google ADK AI agent for unfamiliar descriptions, and surfaces low-confidence results for manual review. Well-trained rules make future imports nearly instant and require progressively less user intervention over time.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `categories`, `categorization_rules`, `outbox` |
| Events published | `CategoryCreated` (`categorization.CategoryCreated`) |
| Events consumed | None |
| Temporal workflows | None — `suggest_category()` is a synchronous Pattern 3 direct service call invoked from within the `statements` domain's Temporal activity |
| Slices covered | 10, 17, 18, 19, 20, 21 |

---

## Test Scenarios

---

### Scenario 1: Browse Default and Custom Categories

**Source slice**: `docs/slices/17-browse-categories.md`
**Business intent**: A user opening the category list sees all 22 system defaults plus any custom categories they have created, grouped by kind.
**Domains involved**: categorization

#### Preconditions
- User is authenticated.
- Database has been seeded with system defaults (15 expense + 6 income + 1 transfer = 22 categories with `user_id = NULL`, `is_active = true`).
- User has no custom categories (new-user baseline).

#### Steps
1. `GET /api/v1/categories/` with the authenticated user's token.
2. Assert the full default list is returned.
3. Create one custom category (`POST /api/v1/categories/`, `kind = 'expense'`, `name = 'Pet Care'`).
4. Re-fetch `GET /api/v1/categories/`.
5. Toggle "Show inactive categories" — re-fetch without the `is_active` filter.

#### Assertions
- **DB**: `SELECT count(*) FROM categories WHERE user_id IS NULL AND is_active = true` returns exactly 22 after seeding.
- **API response** (step 2): Response contains exactly 22 items. Each item has `id`, `name`, `slug`, `kind`, `icon`, `is_default`. No item has a private `user_id` field exposed. Categories are present for kinds: `expense` (15), `income` (6), `transfer` (1).
- **API response** (step 4): Response contains 23 items. The new "Pet Care" category appears with `is_default = false` and `kind = 'expense'`.
- **API response** (step 5): Response includes any inactive categories in addition to active ones.
- **Events**: No events published for a browse operation.
- **Side effects**: None — read-only operation.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| New user with zero custom categories | `GET /api/v1/categories/` returns all 22 defaults; no empty state | [ ] |
| Query uses plain `WHERE user_id = :uid` (bug) | Would silently return 0 rows for a new user — this must NOT happen; the view must use `WHERE user_id = :uid OR user_id IS NULL` | [ ] |
| User requests inactive categories toggle | Response includes categories with `is_active = false` that were previously hidden | [ ] |
| Default category `is_active` state | All 22 default categories have `is_active = true` after seeding | [ ] |

---

### Scenario 2: Create a Custom Category

**Source slice**: `docs/slices/18-create-custom-category.md`
**Business intent**: A user adds a personalised category not covered by the defaults so they can use it for transactions, budgets, and rules.
**Domains involved**: categorization

#### Preconditions
- User is authenticated.
- System defaults are seeded.

#### Steps
1. `POST /api/v1/categories/` with body `{ "name": "Pet Care", "kind": "expense", "icon": "🐾" }`.
2. Query the `categories` table directly to verify the row.
3. `GET /api/v1/categories/` to confirm the new category appears in the user's list.
4. Attempt `POST /api/v1/categories/` with `{ "name": "Pet Care", "kind": "expense" }` again (duplicate name).
5. Attempt `POST /api/v1/categories/` with `{ "name": "Pocket Money", "kind": "transfer" }` (reserved kind).

#### Assertions
- **DB** (step 2): A row exists in `categories` with `user_id = <authenticated user's UUID>`, `name = 'Pet Care'`, `kind = 'expense'`, `is_default = false`, `is_active = true`, and a `slug` derived from the name (e.g., `pet-care`).
- **API response** (step 1): HTTP 201. Response body contains the new category's `id`, `name`, `slug`, `kind`, `is_default = false`, `is_active = true`.
- **API response** (step 4): HTTP 201 (duplicate names are allowed; the UI should warn but not block). Two separate rows exist with different `id` values.
- **API response** (step 5): HTTP 422 or 400. Transfer kind is reserved for the system's "Self Transfer" category; users cannot create transfer-kind categories.
- **Events**: `CategoryCreated` event published to the outbox after step 1 with `category_id`, `user_id`, `name = 'Pet Care'`, `kind = 'expense'`.
- **Side effects**: The new category is immediately visible in `categories_for_user` view (no migration or cache flush needed). The category is available in the category picker for transactions and statement classification.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Name duplicates a system default (e.g., "Food & Dining") | Allowed — a user-owned row is inserted alongside the default; both exist with different `user_id` values | [ ] |
| Name duplicates an existing custom category | Allowed (no uniqueness constraint enforced by the API); UI should warn | [ ] |
| `kind = 'transfer'` submitted | HTTP 4xx rejection; no row inserted | [ ] |
| `name` field omitted | HTTP 422 validation error | [ ] |
| `icon` field omitted | Row inserted with `icon = NULL` or a sensible default; not a blocking error | [ ] |
| `CategoryCreated` outbox event idempotency | If the outbox poller delivers the event twice, the downstream handler must be idempotent | [ ] |

---

### Scenario 3: `suggest_category()` — Rule Match Path (confidence = 1.0)

**Source slice**: `docs/slices/19-create-categorization-rule.md`
**Business intent**: A user-defined rule fires automatically for known merchants, returning `confidence=1.0, source='rule'` so the workflow never pauses for user input.
**Domains involved**: categorization, statements (caller)

#### Preconditions
- User is authenticated.
- An active `categorization_rules` row exists: `pattern = 'swiggy'`, `match_type = 'contains'`, `category_id = <Food & Dining UUID>`, `priority = 10`, `is_active = true`.
- No higher-priority rule exists that would match the test description.

#### Steps
1. Call `suggest_category(description='UPI/123456/SWIGGYORD', user_id=<uid>, amount=350.0, context={})`.
2. Verify the returned `CategorySuggestion`.
3. Call `suggest_category` with a description that does NOT match any rule (e.g., `'NEFT CR/ABCDE/UNKNOWN MERCHANT'`) to confirm the AI path is reached.

#### Assertions
- **Return value** (step 2): `category_id = <Food & Dining UUID>`, `confidence = 1.0`, `source = 'rule'`. No ADK API call is made (verify via mock/spy — the ADK client must not be invoked).
- **DB**: No row written — `suggest_category()` is read-only for the rule path.
- **Events**: None.
- **Side effects**: Rule evaluation is case-insensitive (`'SWIGGYORD'` matches the pattern `'swiggy'`).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Multiple rules match; different priorities | The rule with the highest `priority` value wins | [ ] |
| Two rules share the same priority | First match in insertion order wins; deterministic within a single query | [ ] |
| Rule `match_type = 'starts_with'` | Matches only if `raw_description` starts with the pattern (case-insensitive) | [ ] |
| Rule `match_type = 'exact'` | Matches only if `raw_description` equals the pattern exactly (case-insensitive) | [ ] |
| Rule `match_type = 'regex'`, valid pattern | Matches if description satisfies the compiled regex (e.g., `^UPI/\d+/ZOMATO`) | [ ] |
| Rule `match_type = 'regex'`, invalid pattern stored | TODO: clarify whether the service should skip/log invalid stored regex patterns or raise | [ ] |
| Rule `is_active = false` | Inactive rule is never evaluated; falls through to AI path | [ ] |
| ~~`amount_gte` / `amount_lte` / `source_account_id` conditions~~ | **These columns do not exist in the current schema** (`categorization_rules` only has `pattern` and `match_type`). Tests for amount-based or account-scoped rules cannot be written until these columns are added. See TODO. | N/A |

---

### Scenario 4: `suggest_category()` — ADK AI Path, High Confidence (≥ 0.85)

**Source slice**: `docs/slices/10-classify-low-confidence-rows.md`, `docs/slices/19-create-categorization-rule.md`
**Business intent**: When no rule matches, the ADK agent suggests a category; if confidence ≥ 0.85 the suggestion is accepted automatically without pausing the workflow.
**Domains involved**: categorization, statements (caller)

#### Preconditions
- User is authenticated.
- No `categorization_rules` rows exist for this user (or none match the test description).
- ADK client is mocked to return `{ category: "Food & Dining", confidence: 0.92 }`.

#### Steps
1. Call `suggest_category(description='ZOMATO ORDER 98765', user_id=<uid>, amount=220.0, context={})`.
2. Verify the `CategorySuggestion` returned.
3. Verify the ADK client was called with the description, amount, user's full category list (defaults + custom), and recent context.

#### Assertions
- **Return value**: `category_id = <Food & Dining UUID>`, `confidence = 0.92`, `source = 'ai'`. `item_suggestions` may contain AI-suggested item labels or an empty list.
- **DB**: No row written.
- **Events**: None.
- **Side effects**: The ADK call includes the user's custom categories in the prompt (via `WHERE user_id = :uid OR user_id IS NULL` query) so newly created custom categories are immediately usable.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| ADK returns confidence exactly 0.85 | Treated as high-confidence (threshold is `< 0.85` for low confidence); workflow does not pause | [ ] |
| ADK returns confidence 0.84 | Treated as low-confidence; workflow pauses for user input (Scenario 5 covers this path) | [ ] |
| ADK is unavailable / times out | TODO: clarify error handling — should `suggest_category()` return `source='none'` or propagate the exception to the Temporal activity? | [ ] |
| User has custom categories; ADK should see them | ADK prompt context includes all active categories from `categories_for_user` view | [ ] |

---

### Scenario 5: `suggest_category()` — ADK AI Path, Low Confidence (< 0.85) → Manual Classification

**Source slice**: `docs/slices/10-classify-low-confidence-rows.md`
**Business intent**: When AI confidence falls below 0.85, the workflow pauses and the user manually assigns a category to the row.
**Domains involved**: categorization (suggest_category), statements (workflow + classify endpoint)

#### Preconditions
- A `StatementProcessingWorkflow` is in progress (`extraction_jobs.status = 'awaiting_input'`).
- At least one `raw_extracted_rows` row has `classification_status = 'pending'`.
- No matching rule exists for the test description.
- ADK client is mocked to return `{ category: "Others", confidence: 0.60 }`.

#### Steps
1. Workflow calls `suggest_category(description='NEFT/HDFC/CR/MISC99', user_id=<uid>, amount=1500.0, context={})`.
2. Verify the low-confidence suggestion is returned.
3. The SSE stream delivers the row to the frontend with `needs_classification: true`.
4. `POST /statements/{job_id}/rows/{row_id}/classify` with `{ "category_id": "<Food & Dining UUID>", "items": [] }`.
5. Verify the Temporal signal was sent and the workflow recorded the classification.
6. Verify the workflow incremented `extraction_jobs.classified_rows` and checked for remaining pending rows.

#### Assertions
- **Return value** (step 2): `confidence = 0.60`, `source = 'ai'`, `category_id = <Others UUID>` (the AI suggestion shown as a pre-selection in the UI if confidence ≥ 0.5).
- **DB** (after step 4): `raw_extracted_rows` row has `classification_status = 'user_classified'`, `final_category_id = <Food & Dining UUID>`, `final_items = []`.
- **DB** (after step 4): `extraction_jobs.classified_rows` is incremented by 1.
- **API response** (step 4): HTTP 200.
- **Events**: No categorization domain events; the workflow signal is handled entirely within the statements domain.
- **Side effects**: If more pending rows remain, the workflow enters the next `waitForSignal`; if all rows are classified, `ExtractionCompleted` is published (statements domain).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| AI confidence < 0.5 | No pre-selected suggestion shown; user must pick from scratch | [ ] |
| User submits an income-kind category for a debit row | HTTP 4xx validation error: `category.kind` must match the transaction type (`debit → expense or transfer`) | [ ] |
| User submits an expense-kind category for a credit row | HTTP 4xx validation error: `category.kind` must be `income` or `transfer` | [ ] |
| Item amounts submitted that do not sum to transaction total | HTTP 4xx (or frontend-blocked) — item amounts must equal the transaction amount | [ ] |
| User marks the row as skipped | `classification_status = 'skipped'`; no transaction is created from this row | [ ] |
| User closes the browser mid-classification | Temporal workflow remains in `awaiting_input`; user can resume from the Statements screen | [ ] |

---

### Scenario 6: `suggest_category()` — Self Transfer Shortcut

**Source slice**: `docs/slices/19-create-categorization-rule.md`
**Business intent**: Any transaction whose `type` is `'transfer'` is assigned to "Self Transfer" unconditionally, before any rule or AI check runs.
**Domains involved**: categorization

#### Preconditions
- System default "Self Transfer" category is seeded (`kind = 'transfer'`, `is_default = true`, `user_id = NULL`).
- A user rule exists that would otherwise match the test description (to confirm the transfer shortcut takes precedence).

#### Steps
1. Call `suggest_category(description='NEFT/SELF/SAVINGS1234', user_id=<uid>, amount=10000.0, context={ 'transaction_type': 'transfer' })`.
2. Verify the result.

#### Assertions
- **Return value**: `category_id = <Self Transfer UUID>`, `confidence = 1.0`, `source = 'rule'`. No user-defined rule is evaluated; no ADK call is made.
- **DB**: No row written.
- **Events**: None.
- **Side effects**: None. The "Self Transfer" category is excluded from budget and earnings calculations (enforced by those domains' queries, not by this domain).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User-defined rule matches the same description | Rule is not evaluated; `transaction_type = 'transfer'` always takes precedence (Step 0 in resolution order) | [ ] |
| ADK would have returned a different suggestion | ADK is not called; Self Transfer is returned regardless | [ ] |
| "Self Transfer" category is missing from seed data | `suggest_category()` should raise a clear internal error rather than returning `category_id = None` | [ ] |

---

### Scenario 7: Create a Categorization Rule

**Source slice**: `docs/slices/19-create-categorization-rule.md`
**Business intent**: A user defines a pattern so that known merchants are classified deterministically on every future import, bypassing the AI.
**Domains involved**: categorization

#### Preconditions
- User is authenticated.
- "Food & Dining" category exists (system default).

#### Steps
1. `POST /api/v1/categorization-rules/` with body `{ "pattern": "swiggy", "match_type": "contains", "category_id": "<Food & Dining UUID>", "priority": 10 }`.
2. Verify the `categorization_rules` row in the DB.
3. `POST /api/v1/categorization-rules/` with body `{ "pattern": "^UPI/\\d+/ZOMATO", "match_type": "regex", "category_id": "<Food & Dining UUID>", "priority": 5 }`.
4. Attempt `POST /api/v1/categorization-rules/` with an invalid regex: `{ "pattern": "[invalid(", "match_type": "regex", ... }`.

#### Assertions
- **DB** (step 2): A `categorization_rules` row exists with `user_id = <uid>`, `pattern = 'swiggy'`, `match_type = 'contains'`, `category_id = <Food & Dining UUID>`, `priority = 10`, `is_active = true`.
- **API response** (step 1): HTTP 201. Response contains the new rule's `id` and all submitted fields.
- **API response** (step 3): HTTP 201. Regex pattern stored correctly.
- **API response** (step 4): HTTP 422 or 400. Invalid regex rejected before storage.
- **Events**: No events published for rule creation.
- **Side effects**: Rule takes effect immediately on the next `suggest_category()` call — no restart or cache clear required.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Very broad pattern (e.g., `"NEFT"`) | Accepted (no server-side rejection for broad patterns; UI may warn) | [ ] |
| `priority` field omitted | Defaults to 0 | [ ] |
| `match_type = 'starts_with'`, description starts with pattern | Rule matches | [ ] |
| `match_type = 'exact'`, description has trailing whitespace | Behaviour depends on trim normalisation — TODO: confirm whether the service trims descriptions before exact match | [ ] |
| `category_id` references a category belonging to a different user | Should be rejected (403 or 422) — TODO: confirm whether the service validates category ownership | [ ] |
| `category_id` references a non-existent category | Should be rejected (422); note `categorization_rules.category_id` has no PG FK per the domain doc | [ ] |

---

### Scenario 8: Manage Categorization Rules (Edit, Prioritise, Deactivate, Delete)

**Source slice**: `docs/slices/20-manage-categorization-rules.md`
**Business intent**: Users can update, reorder, disable, and delete existing rules so the classification engine stays accurate as their transaction patterns change.
**Domains involved**: categorization

#### Preconditions
- User is authenticated.
- Two `categorization_rules` rows exist:
  - Rule A: `pattern = 'swiggy'`, `match_type = 'contains'`, `priority = 10`, `is_active = true`
  - Rule B: `pattern = 'zomato'`, `match_type = 'contains'`, `priority = 5`, `is_active = true`

#### Steps
1. `GET /api/v1/categorization-rules/` — verify both rules returned.
2. `PATCH /api/v1/categorization-rules/{rule_a_id}` — change `priority` to 20 and `pattern` to `'swiggy food'`.
3. `PATCH /api/v1/categorization-rules/{rule_b_id}` — set `is_active = false` (deactivate).
4. `DELETE /api/v1/categorization-rules/{rule_b_id}` → 204 — hard delete.
5. `GET /api/v1/categorization-rules/` — verify final state.

#### Assertions
- **API response** (step 1): Both rules returned; active rules listed before inactive.
- **DB** (step 2): Rule A has `pattern = 'swiggy food'`, `priority = 20`, `updated_at` refreshed.
- **DB** (step 3): Rule B has `is_active = false`. Row still exists.
- **DB** (step 4): Rule B row no longer exists in `categorization_rules`.
- **API response** (step 5): Only Rule A returned. Rule B is gone.
- **Events**: No events published for rule management operations.
- **Side effects**: Changes to rules take effect on the next `suggest_category()` call only. Existing transactions previously classified by a rule are NOT retroactively changed. Existing transactions classified as "Others" before a rule existed are NOT retroactively re-classified when that rule is created.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Re-activating a deactivated rule | `PATCH` sets `is_active = true`; rule evaluates on next import | [ ] |
| Setting priority to a very large number (e.g., 9999) | Accepted; that rule is always checked first | [ ] |
| Two rules left with the same priority after an edit | Both evaluate; first in insertion order wins — user should use distinct priorities | [ ] |
| Deleting a rule used to classify past transactions | Past transactions are unaffected; only future classification is impacted | [ ] |
| Editing a rule to have an invalid regex pattern | HTTP 4xx rejection; existing rule unchanged | [ ] |

---

### Scenario 9: Classify an Ambiguous Credit Transaction (Slice 21)

**Source slice**: `docs/slices/21-classify-ambiguous-credit.md`
**Business intent**: When a credit transaction cannot be confidently identified as income or a peer repayment, the user is notified and chooses its correct classification so that income totals and peer balances are accurate.
**Domains involved**: earnings (primary), notifications, peers (optional), categorization (upstream taxonomy)

#### Preconditions
- A credit transaction exists in `transactions` with `type = 'credit'`.
- The `earnings` domain processed `TransactionCreated` and published `EarningClassificationNeeded` (confidence below the earnings domain's threshold).
- An in-app notification exists with deep-link `/earnings/classify?transaction_id={id}`.

#### Steps
1. Simulate the notification tap: `GET /earnings/classify?transaction_id={id}` (or navigate to the deep-link).
2. Verify the classification screen data returned.
3. Submit classification as **Income** (sub-scenario A).
4. Reset and submit classification as **Peer repayment** (sub-scenario B).
5. Reset and submit classification as **Ignore / Refund** (sub-scenario C).
6. Attempt a second "Income" classification on the same transaction (idempotency check).

#### Assertions

**Sub-scenario A — Income:**
- **DB**: An `earnings` row is created with `transaction_id` linked, `source_type` matching the selected income type.
- **API response**: HTTP 200 or 201. Notification marked resolved.
- **Events**: `EarningRecorded` published.

**Sub-scenario B — Peer repayment:**
- **DB**: No `earnings` row created. If the user linked a peer balance, a `peer_balances` entry is updated.
- **API response**: HTTP 200.
- **Events**: No `EarningRecorded` published.

**Sub-scenario C — Ignore (Refund / Cashback):**
- **DB**: No `earnings` row created. Transaction remains in `transactions` with its existing category (unchanged).
- **API response**: HTTP 200. Notification marked resolved.
- **Events**: None.

**Idempotency check (step 6):**
- **DB**: No second `earnings` row inserted (the handler checks for an existing row with `transaction_id`). Either returns 200 (no-op) or 409 with a clear message.
- **Events**: `EarningRecorded` not published again.

#### Edge Cases (Ambiguous Credit Classification Types)

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| **Income — Salary** | `earnings` row with `source_type = 'salary'`; `EarningRecorded` published | [ ] |
| **Income — Freelance** | `earnings` row with `source_type = 'freelance'` | [ ] |
| **Income — Rental** | `earnings` row with `source_type = 'rental'` | [ ] |
| **Income — Dividend** | `earnings` row with `source_type = 'dividend'` | [ ] |
| **Income — Interest** (e.g., bank interest credit) | `earnings` row with `source_type = 'interest'`; user selects "Income → Interest" | [ ] |
| **Income — Business** | `earnings` row with `source_type = 'business'` | [ ] |
| **Income — Other** | `earnings` row with `source_type = 'other'` | [ ] |
| **Refund / Cashback** (Ignore path) | No `earnings` row; transaction kept as-is; notification resolved | [ ] |
| **Peer repayment** without linking a peer balance | No `earnings` row; no `peer_balances` change; notification resolved | [ ] |
| **Peer repayment** linked to an existing peer balance | `peer_balances` entry updated to reflect the settlement | [ ] |
| **Transfer** (credit from own account) | TODO: clarify whether the Self Transfer path in `suggest_category()` would have already classified this; if so, `EarningClassificationNeeded` should not have been published. Add a guard test. | [ ] |
| User dismisses the notification without classifying | Transaction remains uncategorised for income purposes; notification stays unread; user can return later | [ ] |
| Same transaction classified as income twice | Second submission blocked or treated as no-op (idempotency); `EarningRecorded` not published twice | [ ] |

---

## Known Inconsistencies

### [1.1] Default category deactivation

**Conflict**: `docs/business-intent/categorization.md` (User Interaction table) states users can "Disable a category — hide categories they never use (e.g., 'Subscriptions')". `docs/slices/17-browse-categories.md` (Edge Cases) states that setting `is_active = false` for a system default is "only possible for user-created categories; system defaults cannot be deactivated by users directly."

**Test impact**: A test that attempts to deactivate a default category (e.g., "Subscriptions") will fail or pass depending on which behaviour is implemented. Do not write this test until the behaviour is resolved. Currently, Scenario 1 only tests toggling inactive visibility (read path), not attempting to deactivate a default.

**Resolution needed**: Decide whether the API should allow `PATCH /api/v1/categories/{category_id}` with `is_active = false` for default categories. Note: there is no DELETE endpoint for categories — deactivation is the only supported removal mechanism (via `PATCH` with `is_active = false`), and this applies only to user-created categories. If not, the business intent user story "hide unused categories" cannot be satisfied for any of the 22 defaults.

### [1.3] "Investment — SIP" category name

**Conflict**: `docs/domains/categorization.md` lists 15 seeded expense defaults including "Investments (outflow)" — there is no "Investment — SIP" category. `docs/slices/30-confirm-sip-detection.md` (Step 3a) references updating a transaction's category to "Investment — SIP".

**Test impact**: Any test that expects a category named "Investment — SIP" to exist in the seeded data will fail. Sub-categories are marked as future use (`parent_id` column is reserved). Do not add a test for this category name until the seeded data and the SIP slice are aligned.

**Resolution needed**: Either add "Investment — SIP" as a sub-category of "Investments (outflow)" in the seed data and document it, or update slice 30 to reference "Investments (outflow)".

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| ~~`amount_gte` / `amount_lte` / `source_account_id` conditions on categorization rules~~ | **Confirmed absent**: these columns do not exist in `categorization_rules` (verified against `src/elixir/domains/categorization/models.py`). The table only has `pattern` and `match_type` as matching conditions. | Do not write tests for these non-existent columns. If they are added in future, document them first and then add tests to Scenarios 3 and 7. |
| `suggest_category()` error handling when ADK is unavailable | Not documented in any slice or domain doc | Define expected behaviour (return `source='none'`? raise? retry?) and add to Scenario 4 |
| `match_type = 'exact'` whitespace normalisation | Trim behaviour before exact match not documented | Confirm and add edge case to Scenario 7 |
| Category ownership validation in rule creation | Whether `category_id` must belong to the requesting user is not documented | Confirm and add edge case to Scenario 7 |
| Default category deactivation API behaviour | See Inconsistency 1.1 | Resolve inconsistency, then add test |
| `suggest_category()` behaviour when "Self Transfer" seed row is missing | Not covered | Add to Scenario 6 edge cases once confirmed |
| Override of auto-classified (high-confidence) rows during statement review | Gap 3.4 in INCONSISTENCIES.md — the user can tap any auto-classified row to change its category | Needs a separate slice/test; not currently in scope for these 6 slices |
| `suggest_category()` returning `source='none'` (no rule, ADK unavailable or returns nothing) | Resolution order step 4 implies a low-confidence return, but a `source='none'` path is not documented | Clarify and add test |
| Slice 21 — Transfer credit guard | A credit from the user's own account should have been classified as "Self Transfer" before `EarningClassificationNeeded` fires; test that this guard exists | See Scenario 9 edge cases |

---

## TODO

- [ ] Resolve inconsistency 1.1 (default category deactivation) before writing the "hide a default category" test.
- [ ] Resolve inconsistency 1.3 ("Investment — SIP" category) before writing any SIP-related categorization tests.
- [x] ~~Confirm whether `amount_gte`, `amount_lte`, and `source_account_id` are real columns in `categorization_rules`~~ ✅ Resolved: these columns do NOT exist in the schema (confirmed via `src/elixir/domains/categorization/models.py`). The `categorization_rules` table only supports `pattern` and `match_type` as matching conditions. Scenario 3 edge case table updated.
- [ ] Confirm whether amount_gte, amount_lte, source_account_id conditions are planned — they are referenced in older test scenario drafts but absent from the model schema. Do not write tests for non-existent columns.
- [ ] Define and document `suggest_category()` error behaviour when the ADK agent is unavailable or returns an empty result.
- [ ] Confirm trim/normalisation behaviour for `match_type = 'exact'` rules.
- [ ] Confirm whether the rule creation endpoint validates that `category_id` belongs to the requesting user (or is a system default accessible to them).
- [ ] Add Playwright E2E tests for the frontend category picker and rule management screens once the API contract is stable.
- [ ] Link each scenario to its corresponding pytest test file path once tests are written (suggested location: `tests/e2e/categorization/`).
- [x] ~~Confirm the exact endpoint paths for category and rule CRUD~~ ✅ Resolved: confirmed routes are:
  - `GET /api/v1/categories/`, `POST /api/v1/categories/` → 201, `PATCH /api/v1/categories/{category_id}` → 200
  - No DELETE endpoint for categories — deactivation via `PATCH` with `is_active = false` only
  - `GET /api/v1/categorization-rules/`, `POST /api/v1/categorization-rules/` → 201, `PATCH /api/v1/categorization-rules/{rule_id}` → 200, `DELETE /api/v1/categorization-rules/{rule_id}` → 204
  All placeholder paths in this guide have been updated.
