# Slice: Re-Upload After Partial Statement Import

## User Goal
Recover the transactions that were discarded when a statement processing workflow timed out before all rows were classified.

## Trigger
User receives a notification: "Statement partially imported — {n} transactions saved. Rows from {discarded_from_date} to {discarded_to_date} were discarded. Upload the statement again to process the remaining rows."

## Preconditions
- A prior `statement_uploads` row exists with `status = 'partial'`.
- The corresponding `extraction_jobs` row has `status = 'partial'`.
- The user still has access to the original statement file.

## Steps

### Step 1: Receive Partial Import Notification
**User action**: Taps the "Statement partially imported" notification.
**System response**: Deep-link opens the statement upload screen, pre-selecting the account from the original upload. The notification body shows the discarded date range (`discarded_from_date` to `discarded_to_date`) so the user knows exactly what is missing.

### Step 2: Re-Upload the Same Statement File
**User action**: Selects the same account and re-uploads the original file (same PDF or CSV).
**System response**: A new `statement_uploads` row is created. A new `extraction_jobs` row and `StatementProcessingWorkflow` are started. The old partial upload row remains in history (`status = 'partial'`).

### Step 3: Overlap Warning
**User action**: None.
**System response**: During parsing, the workflow detects overlap with the prior partial upload (same account, overlapping date range). An SSE warning is shown:
> "This statement overlaps with a previously imported statement from {period_start} to {period_end}. Duplicate transactions will be skipped automatically."

Processing continues — this is expected behaviour for a re-upload.

### Step 4: Classification Proceeds
**User action**: Classifies any low-confidence rows as normal.
**System response**: The workflow processes all rows. When a row's fingerprint already exists in `transactions` (from the partial import), the `transactions` domain handler skips it (idempotent deduplication). Only rows from the discarded date range produce new transactions.

### Step 5: New Transactions Created
**User action**: None.
**System response**: `ExtractionCompleted` is published. `transactions` domain creates only the new (non-duplicate) rows. A "Statement processed" notification shows the count of net-new transactions.

## Domains Involved
- **statements**: Manages partial status, runs the new workflow, emits overlap warning SSE.
- **categorization**: Classifies rows again (rules + AI — same behaviour as initial upload).
- **transactions**: Skips duplicate fingerprints; creates only genuinely new rows.
- **notifications**: Creates the partial import warning (Step 1) and the completion banner (Step 5).

## Edge Cases & Failures
- **User uploads a different file for the same account**: The system processes it as a fresh statement. Any overlap is warned about and duplicates are skipped by fingerprint. No special handling needed.
- **All rows from the re-upload are duplicates**: `transactions` domain skips all rows. User sees "0 new transactions". This happens if the previously classified rows already covered the full statement — the re-upload was unnecessary but harmless.
- **The discarded rows also have low-confidence classification**: The workflow pauses for user input just as it did the first time. The user must classify them again.
- **User ignores the notification**: The partial upload remains in history. The missing transactions are simply absent from the ledger. The user can re-upload at any time.

## Success Outcome
All transactions from the statement are now in the ledger. Duplicates from the first (partial) import were automatically skipped.
