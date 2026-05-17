# statements — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

From a user's perspective, the statements domain turns a raw bank or credit card file into a reviewed, categorised set of transactions without requiring manual data entry. The user uploads a PDF or CSV statement, watches rows stream in as the AI classifies them in real time, confirms or corrects any row the AI was unsure about, and finishes with all transactions committed to their ledger. The domain is explicitly designed to be interruptible: if the user closes the app mid-review, the Temporal workflow holds all progress durably and the user can return to exactly the row they left off. If too much time elapses (7-day timeout), any rows already classified are committed as a partial import and the user is told which date range to re-upload.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `statement_uploads`, `extraction_jobs`, `raw_extracted_rows`, `outbox` |
| Events published | `StatementUploaded`, `ExtractionCompleted`, `ExtractionPartiallyCompleted` |
| Events consumed | None — the domain is triggered by HTTP upload, not domain events |
| Temporal workflows | `StatementProcessingWorkflow` (on-demand, triggered by `POST /statements/upload`) |
| Slices covered | 09, 10, 11, 12 |

---

## Test Scenarios

---

### Scenario 1: Happy Path — Upload, Parse, Auto-Classify, Complete

**Source slice**: `docs/slices/09-upload-bank-statement.md`
**Business intent**: A user uploads a statement where all rows are classified at high confidence, resulting in a full set of committed transactions with no user input required beyond the initial upload.
**Domains involved**: statements, categorization, transactions, notifications

#### Preconditions
- An authenticated user exists with at least one active bank account registered.
- A valid PDF or CSV statement file is available (all rows will yield AI confidence ≥ 0.85).
- No prior statement for the same account and overlapping date range exists (to avoid the overlap warning path — covered in Scenario 5).

#### Steps

1. `POST /statements/upload` (multipart: `file`, `account_id`, `account_kind`) → `201 Created`; response contains `{job_id, stream_url}`.
2. DB immediately after upload: `statement_uploads.status = 'uploaded'`, `extraction_jobs.status = 'queued'`, `extraction_jobs.temporal_workflow_id` is set.
3. `GET /statements/{job_id}/stream` → SSE connection opened; client receives a stream of `row_update` events.
4. Parsing activity runs: `extraction_jobs.status` transitions `'queued'` → `'parsing'` → `'classifying'`; `extraction_jobs.total_rows` is set to the number of rows found; `statement_uploads.period_start` and `period_end` are set.
5. File deleted from storage after parsing: `statement_uploads.file_path` no longer resolves to an existing object in the file store.
6. For each high-confidence row: SSE emits `{event: "row_update", data: {row_id, status: "auto_classified", ai_suggestion: {category_id, confidence, item_suggestions}}}`.
7. All rows classified: SSE emits `{event: "job_completed", data: {job_id, total_rows, classified_rows, skipped_rows: 0}}`; stream closes.
8. `ExtractionCompleted` outbox row is written in the same transaction as `extraction_jobs.status = 'completed'` and `statement_uploads.status = 'completed'`.
9. Outbox poller dispatches `ExtractionCompleted` to `transactions` domain handler.
10. Notifications domain handler creates a "Statement processed" in-app notification.

#### Assertions

- **DB**: `extraction_jobs.status = 'completed'`, `extraction_jobs.classified_rows = extraction_jobs.total_rows`, `extraction_jobs.completed_at IS NOT NULL`.
- **DB**: `statement_uploads.status = 'completed'`, `statement_uploads.period_start IS NOT NULL`, `statement_uploads.period_end IS NOT NULL`.
- **DB**: Every `raw_extracted_rows` row for this job has `classification_status = 'auto_classified'` and `final_category_id IS NOT NULL`.
- **DB**: File is deleted from storage — the file_path in `statement_uploads` does not correspond to an existing stored object.
- **DB**: `transactions` rows exist for each non-duplicate row in `classified_rows`, each with a valid `fingerprint`.
- **API response**: `GET /statements/{job_id}` returns `status = 'completed'`, `classified_rows = total_rows`.
- **SSE**: At least one `row_update` event with `status: "auto_classified"` was received before `job_completed`.
- **Events**: `ExtractionCompleted` event present in outbox with correct `job_id`, `upload_id`, `user_id`, `account_id`, `account_kind`, and non-empty `classified_rows` list.
- **Side effects**: A `notifications` row exists with title "Statement processed" and deep-link `/statements/{job_id}/review`.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| File type is not `pdf` or `csv` | `400 Bad Request`; `extraction_jobs.status = 'failed'`; `error_message` set | [ ] |
| File size exceeds 20 MB | `400 Bad Request` before workflow is triggered | [ ] |
| Parser cannot extract any rows from a valid PDF | `extraction_jobs.status = 'failed'`; `error_message` set; SSE emits error event | [ ] |
| All rows match existing fingerprints (statement already fully imported) | `ExtractionCompleted` published; `transactions` domain skips all rows; notification shows "0 new transactions" | [ ] |
| pdfplumber yields fewer than 3 rows — camelot fallback used | Rows are still extracted successfully via camelot; job proceeds to classifying | [ ] |

---

### Scenario 2: Human-in-the-Loop — Low-Confidence Rows Require User Classification

**Source slice**: `docs/slices/10-classify-low-confidence-rows.md`
**Business intent**: When the AI cannot confidently classify one or more rows (confidence < 0.85), the workflow pauses at each such row, presents it to the user via SSE, and waits for a Temporal signal carrying the user's category choice before continuing.
**Domains involved**: statements, categorization, transactions

#### Preconditions
- An authenticated user exists with at least one active bank account registered.
- A statement file is available that will produce at least one row with AI confidence < 0.85.
- A `StatementProcessingWorkflow` is running and has reached the classification loop.

#### Steps

1. During the SSE stream from `GET /statements/{job_id}/stream`, a `row_update` event arrives with `status: "needs_classification"` and `ai_suggestion: {category_id, confidence: <0.85}`.
2. DB at this point: `raw_extracted_rows.classification_status = 'pending'` for the row; `extraction_jobs.status = 'awaiting_input'`.
3. User selects a category from the UI (confirms or overrides the AI suggestion); optionally adds item breakdown (must sum to transaction amount).
4. `POST /statements/{job_id}/rows/{row_id}/classify` with body `{category_id, items: [{label, amount}] | null}` → `200 OK`.
5. API looks up `extraction_jobs.temporal_workflow_id` and sends a `ClassificationSubmitted` Temporal signal to the running workflow.
6. Workflow receives signal; updates `raw_extracted_rows`: `classification_status = 'user_classified'`, `final_category_id = category_id`, `final_items` set; increments `extraction_jobs.classified_rows`.
7. SSE emits `{event: "row_update", data: {row_id, status: "classified"}}`.
8. Workflow advances to the next row; if more low-confidence rows remain, another `waitForSignal` is entered and the next `needs_classification` SSE event is emitted.
9. When all rows are classified: `ExtractionCompleted` published → `extraction_jobs.status = 'completed'`.

#### Assertions

- **DB**: `raw_extracted_rows.classification_status = 'user_classified'` for the submitted row.
- **DB**: `raw_extracted_rows.final_category_id` matches the `category_id` sent in the signal body.
- **DB**: `raw_extracted_rows.final_items` matches the `items` array if provided.
- **DB**: `extraction_jobs.classified_rows` incremented by 1 after each signal.
- **API response**: `POST /statements/{job_id}/rows/{row_id}/classify` returns `200 OK`.
- **SSE**: A `row_update` event with `status: "classified"` is received for the row after signal submission.
- **Events**: After the last row is classified, `ExtractionCompleted` appears in the outbox.
- **Side effects**: Transactions are created in the `transactions` domain once `ExtractionCompleted` is consumed.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User submits an income category for a debit row | `400 Bad Request`; validation error: category kind does not match transaction type | [ ] |
| Item amounts do not sum to the transaction total | Frontend blocks submission; API should also return `422 Unprocessable Entity` if items are submitted that do not sum correctly | [ ] |
| User skips a row (marks as not a real transaction) | `raw_extracted_rows.classification_status = 'skipped'`; row is excluded from `classified_rows` in `ExtractionCompleted`; no transaction is created for this row | [ ] |
| ADK agent timeout during classification | Row is treated as low-confidence (`confidence < 0.85`); `needs_classification` SSE event emitted; user asked to classify manually | [ ] |
| ADK returns no category | Same as agent timeout — treated as low-confidence | [ ] |

---

### Scenario 3: Override Auto-Classified Row During Review

**Source slice**: `docs/slices/09-upload-bank-statement.md` (Step 4)
**Business intent**: Even after a row is auto-classified at high confidence, the user can change its category during the review phase before the statement is finalised.
**Domains involved**: statements, categorization

#### Preconditions
- A `StatementProcessingWorkflow` is in progress.
- At least one `raw_extracted_rows` row has `classification_status = 'auto_classified'`.

#### Steps

1. During SSE stream, a `row_update` event with `status: "auto_classified"` is received.
2. User taps the row to override its category.
3. `POST /statements/{job_id}/rows/{row_id}/classify` with the new `category_id` → `200 OK`.
4. Temporal signal `ClassificationSubmitted` is sent; workflow records the override.
5. DB updated: `raw_extracted_rows.classification_status = 'user_classified'`, `final_category_id` set to the new category.

#### Assertions

- **DB**: `raw_extracted_rows.classification_status = 'user_classified'` (overwritten from `auto_classified`).
- **DB**: `raw_extracted_rows.final_category_id` reflects the user's chosen category, not the original AI suggestion.
- **API response**: `POST /statements/{job_id}/rows/{row_id}/classify` returns `200 OK`.
- **Events**: The override is captured in the row's final state that flows into `ExtractionCompleted`'s `classified_rows` payload.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Override submitted after `extraction_jobs.status = 'completed'` | `404 Not Found` or `409 Conflict`; workflow is no longer running and cannot receive a signal | [ ] |
| Override submitted with the same category already set | Accepted; `classification_status` remains or transitions to `user_classified`; no error | [ ] |

---

### Scenario 4: Resume Abandoned Statement Classification

**Source slice**: `docs/slices/11-resume-abandoned-statement.md`
**Business intent**: A user who closes the app or navigates away mid-classification can return to the in-progress statement and continue from the exact row where the workflow is paused, without losing any prior work.
**Domains involved**: statements, categorization, transactions, notifications

#### Preconditions
- An `extraction_jobs` row exists with `status = 'awaiting_input'`.
- The 7-day workflow timeout has not elapsed.
- At least one `raw_extracted_rows` row has `classification_status = 'pending'`.
- Some rows have already been classified (`auto_classified` or `user_classified`).

#### Steps

1. User navigates to the Statements screen; the in-progress statement is visible.
2. `GET /statements/{job_id}` → `200 OK`; response includes all `raw_extracted_rows` with their current `classification_status`, `classified_rows`, and `total_rows`.
3. The first row with `classification_status = 'pending'` is identified as the current item needing input.
4. Already-classified rows are displayed as read-only (with option to override).
5. User classifies each remaining pending row via `POST /statements/{job_id}/rows/{row_id}/classify` → Temporal signal → workflow advances.
6. Workflow does not restart — it resumes from the paused `waitForSignal` state.
7. After the last pending row is classified: `ExtractionCompleted` published; `extraction_jobs.status = 'completed'`.

#### Assertions

- **DB**: `GET /statements/{job_id}` returns rows in correct `classification_status` states reflecting prior session work.
- **DB**: Previously `auto_classified` and `user_classified` rows are unchanged after resume.
- **DB**: `extraction_jobs.temporal_workflow_id` is unchanged — same workflow run is continuing, not a new one.
- **DB**: After completing all pending rows: `extraction_jobs.status = 'completed'`, `statement_uploads.status = 'completed'`.
- **API response**: `GET /statements/{job_id}` returns `classified_rows` count matching rows already done, not reset to zero.
- **Events**: `ExtractionCompleted` published at the end with the full `classified_rows` list including rows from both sessions.
- **Side effects**: Transactions created for all rows (including those classified in the prior session — but fingerprint deduplication prevents duplicates if the workflow had already started committing rows).

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| User overrides a previously `auto_classified` row while resuming | `classification_status` becomes `user_classified`; new category recorded; workflow continues | [ ] |
| `extraction_jobs.status = 'completed'` when user tries to resume | `GET /statements/{job_id}` returns read-only summary; classify endpoint returns `409 Conflict` or `404` | [ ] |
| `extraction_jobs.status = 'failed'` when user tries to resume | UI shows error state; no classification possible | [ ] |
| No notification is sent when user abandons mid-classification | No notification row exists in `notifications` for the `awaiting_input` state transition; user must discover via Statements screen | [ ] |

---

### Scenario 5: 7-Day Timeout — Partial Import and Re-Upload

**Source slice**: `docs/slices/12-reupload-partial-statement.md`
**Business intent**: If a user never finishes classifying a statement and the workflow times out after 7 days, all rows classified so far are committed as transactions, unclassified rows are discarded, and the user is notified of exactly which date range is missing so they can re-upload and recover the remaining transactions.
**Domains involved**: statements, transactions, notifications, categorization

#### Preconditions
- A `StatementProcessingWorkflow` is running with `extraction_jobs.status = 'awaiting_input'`.
- At least one row has been classified and at least one row remains `pending`.
- 7 days have elapsed since the workflow entered the pending-input state.

#### Steps

1. Temporal workflow timeout fires (7-day deadline).
2. Workflow publishes `ExtractionPartiallyCompleted` (via outbox) with `classified_rows` (already-done rows) and `discarded_from_date` / `discarded_to_date`.
3. All remaining `raw_extracted_rows` with `classification_status = 'pending'` are marked `skipped`.
4. `extraction_jobs.status = 'partial'`; `statement_uploads.status = 'partial'`.
5. `transactions` domain consumes `ExtractionPartiallyCompleted`; creates transactions for `classified_rows` only.
6. `notifications` domain consumes `ExtractionPartiallyCompleted`; creates a "Statement partially imported" warning notification with discarded date range.
7. User taps notification → deep-link opens upload screen pre-selecting the account from the original upload.
8. User re-uploads the same file → `POST /statements/upload` creates a new `statement_uploads` row and triggers a new `StatementProcessingWorkflow`.
9. During parsing of the re-upload, overlap is detected with the prior partial upload; SSE emits `{type: "overlap_warning", existing_start, existing_end}`.
10. Classification proceeds normally; rows whose fingerprints already exist in `transactions` are skipped by the `transactions` domain handler.
11. Only rows from the discarded date range produce new transactions.
12. `ExtractionCompleted` published for the re-upload; "Statement processed" notification created showing count of net-new transactions.

#### Assertions

- **DB**: `extraction_jobs.status = 'partial'` and `statement_uploads.status = 'partial'` after timeout.
- **DB**: All rows that were `pending` at timeout time have `classification_status = 'skipped'`.
- **DB**: Transactions exist for all rows that had been classified before timeout.
- **DB**: After re-upload, a new `statement_uploads` row and `extraction_jobs` row exist; the old partial rows remain with `status = 'partial'` (history preserved).
- **DB**: Duplicate fingerprints from the first (partial) import are skipped; only genuinely new transactions are created.
- **API response / SSE**: Overlap warning SSE event received during re-upload parsing: `{type: "overlap_warning", existing_start, existing_end}`.
- **Events**: `ExtractionPartiallyCompleted` in outbox with `discarded_from_date`, `discarded_to_date`, and non-empty `classified_rows`.
- **Side effects**: `notifications` row with "Statement partially imported" body exists, containing the discarded date range; deep-link points to the upload screen.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Zero rows classified before timeout | `ExtractionPartiallyCompleted` is not published (no `classified_rows`); `extraction_jobs.status = 'failed'` (no partial data to commit) | [ ] |
| Re-uploaded file has all rows already in `transactions` (fully duplicated) | `transactions` domain skips all rows; "0 new transactions" notification | [ ] |
| Re-uploaded file's discarded rows also contain low-confidence rows | Workflow pauses for user input on those rows as normal | [ ] |
| User ignores the partial notification and never re-uploads | Partial upload remains in history; missing transactions absent from ledger; no further action taken by system | [ ] |

---

### Scenario 6: Overlap Warning for Already-Imported Date Range

**Source slice**: `docs/slices/09-upload-bank-statement.md` (Step 2 overlap check)
**Business intent**: If the uploaded statement's date range overlaps with a previously completed or partial upload for the same account, the user receives an informational SSE warning before rows are streamed — processing is never blocked, and duplicate rows are handled by fingerprint deduplication.
**Domains involved**: statements, transactions

#### Preconditions
- A prior `statement_uploads` row exists with `status IN ('completed', 'partial')` for the same `account_id` and an overlapping date range.
- User uploads a new statement for the same account covering some or all of the same date range.

#### Steps

1. `POST /statements/upload` → `201 Created`; new `statement_uploads` and `extraction_jobs` rows created.
2. Parsing activity completes; `period_start` and `period_end` set on the new upload.
3. Overlap query finds the prior upload: `SELECT id, period_start, period_end FROM statement_uploads WHERE account_id = :account_id AND status IN ('completed', 'partial') AND period_start <= :period_end AND period_end >= :period_start`.
4. SSE emits `{event: "overlap_warning", data: {existing_start, existing_end}}`.
5. Processing continues normally — classification loop proceeds.
6. When `ExtractionCompleted` is consumed by `transactions` domain, rows with existing fingerprints are skipped.

#### Assertions

- **SSE**: `overlap_warning` event received with correct `existing_start` and `existing_end` dates.
- **DB**: New upload proceeds to `status = 'completed'` regardless of overlap; processing is not blocked.
- **DB**: Only transactions with genuinely new fingerprints are created in `transactions`.
- **API response**: `GET /statements/{job_id}` shows completion with correct row counts reflecting skipped duplicates.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Uploaded statement is entirely within a previously imported range | Overlap warning emitted; all rows skipped by fingerprint dedup; "0 new transactions" in notification | [ ] |
| Multiple prior uploads overlap with the new one | SSE warning reflects one representative overlap period (or all overlapping ranges) | [ ] |

---

## Known Inconsistencies

The following inconsistencies from `docs/business-intent/INCONSISTENCIES.md` directly affect test design for this domain. Tests must account for the **actual documented behaviour**, not the behaviour implied by the inconsistent source.

---

**[1.4] Statement resume notification**

`slices/11-resume-abandoned-statement.md` — Trigger section originally read as: "User taps a notification 'Statement partially classified — tap to continue'". However, `domains/notifications.md` lists no event handler corresponding to a workflow paused in `awaiting_input` state. The `ExtractionPartiallyCompleted` event fires on the **7-day timeout**, not on browser close.

**Impact on tests**: Do not assert that a notification is created when the user closes the browser mid-classification. The test for Scenario 4 (resume) must assert the **absence** of any such notification. The notification that does fire is only on timeout (Scenario 5). The user must discover the in-progress statement by navigating to the Statements screen themselves.

---

**[3.3] Users can skip a statement row entirely**

`business-intent/statements.md` does not mention that a user can mark a row as `skipped` during classification. However, `slices/10-classify-low-confidence-rows.md` edge cases document this as a valid action: a row marked `skipped` will never become a transaction, and it is excluded from `ExtractionCompleted`'s `classified_rows` payload.

**Impact on tests**: The skip action must be an explicit edge-case assertion in Scenario 2. The test must verify that a skipped row results in `classification_status = 'skipped'` and no corresponding transaction record.

---

**[3.4] Users can override auto-classified (high-confidence) rows**

`business-intent/statements.md` implies user input is only sought for low-confidence rows: "High-confidence suggestions are applied automatically; low-confidence ones are sent to the user for review." However, `slices/09-upload-bank-statement.md` (Step 4) makes clear that any auto-classified row can be overridden by the user during the review phase.

**Impact on tests**: Scenario 3 covers this override path. Tests must not assume that `auto_classified` rows are immutable — the classify endpoint must be exercised for auto-classified rows and the result validated.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| `POST /statements/upload` request validation: max file size (20 MB) enforcement | `docs/workflows/statement-processing.md` Step 1 | Add a test that uploads a file exceeding 20 MB and asserts `400 Bad Request` before any DB rows are created |
| Server restart mid-workflow resume | `docs/workflows/statement-processing.md` Error Handling — "Server restart mid-workflow: Temporal replays from last durable checkpoint" | Not exercisable in a standard E2E test; requires a Temporal test environment that simulates worker shutdown; note as infrastructure test |
| Transfer-type rows returning "Self Transfer" immediately (confidence = 1.0, source = 'rule') | `docs/slices/09-upload-bank-statement.md` Step 3 | Verify `auto_classified` for transfer rows without ADK agent being called; confidence = 1.0 in `raw_extracted_rows.ai_confidence` |
| Post-import transfer detection scan | `docs/slices/09-upload-bank-statement.md` Step 6 | Verify that after `ExtractionCompleted`, the `transactions` domain triggers a self-transfer detection scan on newly created transactions |
| Item breakdown validation (amounts must sum to transaction total) | `docs/slices/10-classify-low-confidence-rows.md` Step 3 | Add a test that submits items whose amounts do not sum to the transaction total and assert the API returns `422` |
| `GET /statements/{job_id}` returns correct progress counts mid-classification | `docs/slices/11-resume-abandoned-statement.md` Step 1 | Assert `classified_rows` and `total_rows` match DB state at resume time |

---

## TODO

- [ ] Identify or provision a test statement PDF that reliably produces at least one low-confidence row to enable Scenario 2 without mocking the ADK agent.
- [ ] Decide whether ADK agent calls are mocked in E2E tests (via `page.route()` on the backend endpoint) or exercised against a real ADK sandbox — document the decision before writing tests.
- [ ] Implement a Temporal test harness for the 7-day timeout path (Scenario 5); consider using Temporal's `fast_forward_time` capability rather than waiting real time.
- [ ] Confirm whether the classify endpoint (`POST /statements/{job_id}/rows/{row_id}/classify`) returns `404` or `409` when submitted against a completed or failed job — the slice does not specify the exact status code.
- [ ] Resolve inconsistency [1.4] with the team: either define an `AwaitingInput` event that triggers a "resume" push notification, or update `slices/11-resume-abandoned-statement.md` to remove the notification trigger and document the navigate-back-yourself flow as the canonical path.
- [ ] Add a Playwright test that verifies the SSE `overlap_warning` event is rendered visibly to the user in the UI (the overlap warning message text matches the documented format).
- [ ] Write tests for the `fx` domain interaction: verify that any non-INR transaction rows in a statement have their `currency` field correctly set in `ExtractionCompleted`'s `classified_rows` payload.
