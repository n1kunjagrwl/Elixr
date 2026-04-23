# Slice: Resume Abandoned Statement Classification

## User Goal
Return to a statement classification session that was left incomplete (browser closed, app backgrounded, or user navigated away).

## Trigger
User taps a notification ("Statement partially classified — tap to continue") or navigates to the Statements section and sees a statement with status `in_progress`.

## Preconditions
- An `extraction_jobs` row exists with `status = 'awaiting_input'` (workflow paused at `waitForSignal`).
- The 7-day workflow timeout has not elapsed.
- At least one `raw_extracted_rows` row has `classification_status = 'pending'`.

## Steps

### Step 1: Open In-Progress Statement
**User action**: Taps the in-progress statement card or notification deep-link.
**System response**: The frontend calls `GET /statements/{job_id}` which returns:
- All `raw_extracted_rows` for the job, with their current `classification_status`.
- `extraction_jobs.classified_rows` and `total_rows` for a progress indicator.
- The first row with `classification_status = 'pending'` is highlighted as the current item needing input.

### Step 2: Review Already-Classified Rows
**User action**: Scrolls up to see rows that were already classified (auto or user).
**System response**: Auto-classified and user-classified rows are displayed as read-only (with an option to override if desired).

### Step 3: Continue Classifying Pending Rows
**User action**: Classifies each pending row by selecting a category and tapping "Confirm".
**System response**: Each submission sends `POST /statements/{job_id}/rows/{row_id}/classify` → Temporal signal → workflow resumes from its paused state and advances to the next row. The workflow does not restart — it continues from exactly where it paused.

### Step 4: Statement Completes
**User action**: Classifies the last pending row.
**System response**: Workflow exits `waitForSignal` for the last time, publishes `ExtractionCompleted`, and sets `extraction_jobs.status = 'completed'`. Transactions are created by the `transactions` domain. A "Statement processed" notification is created.

## Domains Involved
- **statements**: Maintains durable workflow state via Temporal; exposes the resume endpoint.
- **categorization**: Previously generated the AI suggestions that remain stored on `raw_extracted_rows`.
- **transactions**: Creates records on `ExtractionCompleted`.
- **notifications**: Creates the completion banner.

## Edge Cases & Failures
- **7-day timeout elapsed before user returns**: See slice `12-reupload-partial-statement.md`. The partial path has already fired; classified rows are already transactions. The user must re-upload for the remaining rows.
- **User overrides a previously auto-classified row while resuming**: Allowed. Sending a signal for a row that already has `classification_status = 'auto_classified'` overwrites it with `user_classified` and the new category. The workflow records the override.
- **Job status is 'completed' or 'failed'**: The statement is no longer resumable. The UI shows a read-only summary instead of the classification UI.

## Success Outcome
The user completes classification of all remaining rows and the full statement is committed as transactions — without losing any work done in the prior session.
