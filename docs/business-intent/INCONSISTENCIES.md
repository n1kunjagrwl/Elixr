# Business Intent — Inconsistencies & Gaps

Cross-reference between `docs/business-intent/`, `docs/domains/`, and `docs/slices/`.
Each entry names the source file(s) in conflict and the exact claim that differs.

---

## 1 — Direct Contradictions

### 1.1 Default category deactivation

| Source | Claim |
|---|---|
| `business-intent/categorization.md` — User Interaction table | "Disable a category — Users can hide categories they never use (e.g., 'Subscriptions')" |
| `slices/17-browse-categories.md` — Edge cases | "User has hidden a default category: `is_active = false` was set for that category row (only possible for user-created categories; system defaults **cannot be deactivated by users directly**)" |

**Impact:** The business intent implies users can clean up the category list by hiding any default. The slice says defaults are immutable for end users. If defaults cannot be hidden, new users see 22 categories and can never reduce that list — the "hide unused categories" user story does not work for any default category.

---

### 1.2 Transaction deletion

| Source | Claim |
|---|---|
| `business-intent/transactions.md` — What It Does Not Do | "Does not delete transactions. Once a transaction exists it can only be edited, not removed." |
| `slices/26-budget-alert-response.md` — Edge cases | "Alert fired but spend is now under 80% (e.g., **user deleted a transaction** after the alert): The alert remains…" |

**Impact:** Slice 26's edge case assumes a delete path exists that the business intent and domain doc explicitly exclude. Either transaction deletion is a hidden feature that needs to be documented, or the slice edge case is wrong and should say "user re-categorised a transaction to a different category."

---

### 1.3 "Investment — SIP" category name

| Source | Claim |
|---|---|
| `domains/categorization.md` — default expense categories | Lists 15 defaults including **"Investments (outflow)"** — no "Investment — SIP" category |
| `slices/30-confirm-sip-detection.md` — Step 3a | "The transaction's category may be updated to **'Investment — SIP'** if it was uncategorised" |

**Impact:** Either there is an undocumented sub-category, or the slice should reference "Investments (outflow)". Sub-categories are explicitly marked as future use (the `parent_id` column exists but is reserved). A category that doesn't exist in the seeded data cannot be assigned.

---

### 1.4 Statement resume notification

| Source | Claim |
|---|---|
| `slices/11-resume-abandoned-statement.md` — Trigger | "User taps a notification **'Statement partially classified — tap to continue'**" |
| `domains/notifications.md` — Events Subscribed | Lists 8 events; none correspond to a workflow paused in `awaiting_input` state |

**Impact:** The resume notification described in the trigger does not have a backing event. The `ExtractionPartiallyCompleted` event fires on *timeout*, not on browser close. A user who closes the app mid-classification receives no notification and must discover the in-progress statement by navigating to the Statements screen themselves. Either this notification type needs to be defined and added to the notifications domain, or the slice trigger should be corrected to remove the notification path.

---

### 1.5 SIP registration deactivation notification

| Source | Claim |
|---|---|
| `slices/29-register-sip.md` — Edge cases | "Bank account removed after registration: … **A notification informs the user** that the SIP registration was deactivated." |
| `domains/notifications.md` — Events Subscribed | No notification handler for any `AccountRemoved` or SIP-deactivation event |

**Impact:** Slice 29 promises a notification on SIP deactivation but the notifications domain has no handler for this. The investment domain publishes only `SIPDetected`, `SIPLinked`, and `ValuationUpdated` — none of which cover deactivation. The user's SIP is silently deactivated with no in-app alert.

---

## 2 — Domain Misattribution

### 2.1 Statement date-range overlap detection attributed to `accounts`

| Source | Claim |
|---|---|
| `business-intent/accounts.md` — What It Provides | Lists "Statement date range tracking" as a feature of the accounts domain |
| `domains/accounts.md` — "Statement Date Range Overlap Detection" | The SQL query shown queries `statement_uploads`, which is a table **owned by the `statements` domain**, not `accounts` |
| `domains/statements.md` — `StatementProcessingWorkflow` | The overlap check runs inside the Temporal workflow, entirely within the `statements` domain |

**Impact:** The accounts domain does not own this feature. Overlap detection is a `statements` domain concern. The `accounts` business intent should describe this more accurately as "Enables overlap detection: accounts are the grouping key for which the `statements` domain checks for date-range overlaps." The accounts domain doc section titled "Statement Date Range Overlap Detection" is misleadingly placed.

---

## 3 — Gaps in Business Intent (behaviour in slices/domains not captured)

### 3.1 Logout is device-scoped; multiple sessions exist simultaneously

`business-intent/identity.md` describes login and logout without mentioning that a user can have multiple active sessions on multiple devices simultaneously, and that logging out only revokes the current session.

`slices/02-user-login.md` (edge cases) and `slices/04-user-logout.md` (edge cases) both state this explicitly. The "log out all sessions" flow is also called out as **not supported** in slice 04 — this is a meaningful gap users would expect.

---

### 3.2 Anti-enumeration on login / registration

`business-intent/identity.md` does not mention that the system returns an identical response whether a phone number is registered or not, to prevent user enumeration.

`slices/02-user-login.md` — "The response to the frontend is identical whether the phone exists or not." `slices/02-user-login.md` edge case — "Unknown phone number: the user sees 'OTP sent' but no SMS arrives."

This is a security behaviour with a meaningful UX consequence (user appears to receive an OTP they will never get).

---

### 3.3 Users can skip a statement row entirely

`business-intent/statements.md` describes the low-confidence classification flow but does not mention that a user can explicitly skip a row, marking it as not a real transaction.

`slices/10-classify-low-confidence-rows.md` — "User skips a row: The row can be marked as `skipped` — it will not become a transaction. This is valid for rows the user knows are not real transactions (e.g., opening balance rows on some statement formats)."

This is a meaningful user action with no coverage in the business intent.

---

### 3.4 Users can override auto-classified (high-confidence) rows

`business-intent/statements.md` — "High-confidence suggestions are applied automatically; low-confidence ones are sent to the user for review." This implies the user's input is only sought for low-confidence rows.

`slices/09-upload-bank-statement.md` — Step 4: "User can tap any auto-classified row to override the category." Auto-classified rows are still editable during the review phase.

---

### 3.5 Account reactivation; SIPs are not auto-reactivated

`business-intent/accounts.md` describes deactivation but says nothing about the reverse.

`slices/08-deactivate-account.md` — "Reactivating a soft-deleted account: user navigates to 'Inactive accounts' and restores it. `is_active = true` is set. SIP registrations are NOT automatically re-activated; the user must manually re-enable them."

Both the reactivation flow and the SIP re-enablement caveat are missing from the business intent.

---

### 3.6 Budget tracking does not backfill pre-creation transactions

`business-intent/budgets.md` does not state that a newly created budget starts with `current_spend = 0`, ignoring any transactions that already exist for the period.

`slices/24-create-budget.md` — "Budget created mid-period: The `budget_progress.current_spend` starts at 0. Transactions from the current period that were imported **before** the budget was created are NOT retroactively counted."

This is a meaningful limitation that directly affects user trust in the budget numbers.

---

### 3.7 Ambiguous credit classified as peer repayment can optionally link to a peer balance

`business-intent/earnings.md` — "Peer repayment — selects the peer contact the money came from." Does not mention what happens in the peers domain.

`slices/21-classify-ambiguous-credit.md` — "Optionally, a `peer_balances` entry is linked to record the settlement (if the repayment relates to an existing balance)."

The optional peer-balance linking step connects two domains in a way the earnings business intent doesn't surface.

---

### 3.8 Manual earnings have no deduplication

`business-intent/earnings.md` does not mention deduplication (or its absence) for manual entries.

`slices/22-add-manual-earning.md` — "No fingerprint deduplication applies to manual earnings. The user may inadvertently create a duplicate. The UI could warn if an earning with the same amount and date already exists, but does not block submission."

This is a meaningful constraint absent from the business intent, especially since the transactions domain prominently features deduplication.

---

### 3.9 Settlement corrections use a new entry, not an edit

`business-intent/peers.md` states "Settlements are an append-only log" but doesn't describe what a user does when they make a mistake.

`slices/35-record-peer-settlement.md` — "Correction If Mistake: The user taps 'Add correction' rather than editing the existing settlement. A new `peer_settlements` row is inserted with a correcting amount."

The correction UX pattern is invisible in the business intent and would surprise users expecting an "Edit" button.

---

### 3.10 Multi-currency settlement limitation is more severe than stated

`business-intent/peers.md` — "Does not support multi-currency balances within a single peer relationship."

`slices/35-record-peer-settlement.md` — "Settlement in a different currency than the balance: The system stores the settlement in the entered currency. **The remaining_amount is not automatically reduced** (it's in the balance currency). The user should enter the INR-equivalent amount… This is a known limitation of the current simple ledger design."

The limitation is not just "no multi-currency" — it's that settling in a different currency than the original balance silently fails to reduce `remaining_amount`. A user paying a USD-denominated debt in INR would see their balance unchanged.

---

### 3.11 Bulk import is all-or-nothing (atomic)

`business-intent/import_.md` — "Does not support partial import continuation."

`slices/13-import-csv-bulk.md` — "Large file (1000+ rows): If the workflow fails mid-run, `import_jobs.status = 'failed'` **and no transactions are created** (the batch is atomic at the `ImportBatchReady` level)."

The business intent frames this as "no partial continuation" (implying the user might lose partial progress). The actual behaviour is stronger: a failure means zero rows are committed, which is better for data integrity but means the user starts over entirely. The word "atomic" is meaningful and missing.

---

### 3.12 One holding per instrument per user

`business-intent/investments.md` does not mention that a user can hold each instrument only once (enforced by a unique constraint).

`slices/27-add-investment-holding.md` — "Duplicate holding: If a `holdings` row already exists for the same `user_id` + `instrument_id`, the backend returns a 409 Conflict: 'You already hold this instrument. Edit the existing holding instead.'"

This constraint shapes how a user adds more units to an existing position (they must edit the holding, not add a second one).

---

## 4 — Missing User-Facing Flows (no corresponding slice exists)

These user actions are implied by business intent or domain docs but have no slice documenting the end-to-end steps.

| Missing slice | Where implied |
|---|---|
| **View earnings dashboard / income summary** | `business-intent/earnings.md` — "See how much I earned from freelance work this year" |
| **Edit an existing earning record** | `business-intent/earnings.md` — "if the user changes their mind about a source type"; `slices/23-manage-earning-sources.md` mentions source edits but not earning edits |
| **Edit / delete a peer contact** | `slices/33-add-peer-contact.md` edge case — "Deleting a contact with open balances" implies a delete flow, but no slice covers contact editing or deletion |
| **Edit an investment holding** (update units, cost, etc.) | `slices/27-add-investment-holding.md` and `slices/30-confirm-sip-detection.md` both reference "edit the existing holding" without a corresponding slice |
| **Edit / deactivate a budget goal** | `slices/26-budget-alert-response.md` — Step 4A references "edit budget" inline, but there is no standalone slice |
| **Delete or roll back an import batch** | `slices/13-import-csv-bulk.md` — "The user must delete the import batch manually **(if this feature exists)**" — whether this feature exists is unresolved |
| **Browse / search the transaction list** | Mentioned throughout as "the transaction list" but there is no slice for the core browse experience, filtering, or search |
| **View all earning sources and their totals** | `business-intent/earnings.md` — "see how much I earned from freelance work this year separately from my salary" implies a summary view |

---

## 5 — Summary Counts

| Category | Count |
|---|---|
| Direct contradictions | 5 |
| Domain misattribution | 1 |
| Business intent gaps (behaviour not captured) | 12 |
| Missing slices | 8 |
| **Total items** | **26** |
