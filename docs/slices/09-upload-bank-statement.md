# Slice: Upload Bank Statement

## User Goal
Import transactions from a bank or credit card statement (PDF or CSV) so they appear in the transaction ledger.

## Trigger
User taps "Upload statement" from the accounts screen or from the onboarding nudge notification.

## Preconditions
- User has at least one active bank account or credit card registered.
- The statement file is a PDF or CSV exported from their bank.

## Steps

### Step 1: Select Account and File
**User action**: Selects the account the statement belongs to, picks the file from their device (PDF or CSV), and taps "Upload".
**System response**: File is stored at a user-scoped path. A `statement_uploads` row is created (`status = 'uploaded'`). An `extraction_jobs` row is created (`status = 'queued'`). The `StatementUploaded` event is published. The `StatementProcessingWorkflow` Temporal workflow is triggered.

### Step 2: Statement Parsed
**User action**: Waits — a progress indicator shows "Parsing statement...".
**System response**: The Temporal workflow's parsing activity runs:
- PDF: pdfplumber or camelot extracts rows.
- CSV: csv.DictReader parses columns.
`statement_uploads.period_start` and `period_end` are set to the earliest and latest transaction dates found.
`extraction_jobs.status` → `'parsing'` → then `'classifying'` once rows are extracted. `total_rows` is set.

**Overlap check**: The workflow queries prior completed `statement_uploads` for the same `account_id` to detect date-range overlap. If found, an SSE warning is streamed:
> "This statement overlaps with a previously imported statement from {existing_start} to {existing_end}. Duplicate transactions will be skipped automatically."
Processing continues regardless.

### Step 3: Rows Classified by AI
**User action**: Watches rows stream in via SSE as they are classified.
**System response**: For each extracted row, the workflow calls `categorization.suggest_category(description, user_id, amount)`:
1. If transaction type is 'transfer': "Self Transfer" category returned immediately.
2. If a user-defined categorization rule matches: `confidence=1.0, source='rule'`.
3. Otherwise: ADK agent is called with the description, amount, user's category list, and recent similar transactions as context.

**High-confidence rows (≥0.85)**: `raw_extracted_rows.classification_status = 'auto_classified'`. Streamed to frontend immediately. `extraction_jobs.classified_rows` incremented.

**Low-confidence rows (<0.85)**: `classification_status = 'pending'`, streamed with `needs_classification: true`. Workflow pauses at `waitForSignal` for each such row until user input arrives.

### Step 4: Review Auto-Classified Rows
**User action**: Reviews the streaming list. High-confidence rows show category badges. User can scroll through and optionally adjust any row.
**System response**: User can tap any auto-classified row to override the category. Override sends `POST /statements/{job_id}/rows/{row_id}/classify` with the new category. Temporal signal is sent; workflow records the override and resumes.

### Step 5: All Rows Classified
**User action**: Confirms the final review screen (or the last low-confidence row is classified).
**System response**: `ExtractionCompleted` event is published via outbox with `classified_rows` payload. `extraction_jobs.status = 'completed'`. `statement_uploads.status = 'completed'`. The uploaded file is deleted from storage — only the extracted rows are retained.

### Step 6: Transactions Created
**User action**: None.
**System response**: The `transactions` domain consumes `ExtractionCompleted`. For each row in `classified_rows`, it computes the fingerprint (`SHA-256(lower(trim(description)) + date.isoformat() + str(amount))`). Checks `UNIQUE(user_id, fingerprint)` — if already exists, row is skipped (idempotent). Otherwise, a `transactions` row and one or more `transaction_items` rows are inserted.

Post-import, a transfer detection scan runs on newly created transactions to auto-detect self-transfers between accounts.

### Step 7: Notifications
**User action**: None.
**System response**: The `notifications` domain consumes `ExtractionCompleted` and creates:
- Title: "Statement processed"
- Body: "{n} transactions from your {account_name} statement are ready to review."
- Deep-link: `/statements/{job_id}/review`

## Domains Involved
- **statements**: File storage, workflow orchestration, raw row extraction and staging.
- **categorization**: `suggest_category()` called per row — rules then AI.
- **transactions**: Consumes `ExtractionCompleted`, creates transaction records with deduplication.
- **notifications**: Creates "Statement processed" banner.
- **fx** (indirect): FX rates available for any non-INR transactions.

## Edge Cases & Failures
- **Unsupported file format**: If the parser cannot extract rows, `extraction_jobs.status = 'failed'` and `error_message` is set. User is shown the error and invited to try a different file.
- **Statement already fully imported**: All rows match existing fingerprints. `transactions` domain skips all rows. User sees "0 new transactions" in the review notification.
- **7-day workflow timeout**: See slice `12-reupload-partial-statement.md` — partial import path.
- **File larger than parser capacity**: Parser activity fails. Workflow retries (Temporal activity retry policy). If retries exhausted, job fails with error.

## Success Outcome
All statement transactions appear in the user's transaction ledger, categorised and ready for review. Duplicates from prior uploads are automatically skipped.
