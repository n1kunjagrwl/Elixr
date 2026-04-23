# Slice: Import Bulk Historical Transactions (CSV/XLSX)

## User Goal
Import historical transactions from a personal spreadsheet, a Splitwise export, or any generic CSV file to backfill the transaction ledger.

## Trigger
User navigates to "Import" and uploads a CSV or XLSX file.

## Preconditions
- User is authenticated.
- The file is a CSV or XLSX with transaction data (column names do not need to match Elixir's schema — mapping happens interactively).

## Steps

### Step 1: Upload File
**User action**: Selects the file and taps "Import".
**System response**: File is stored at a user-scoped path. An `import_jobs` row is created (`status = 'uploaded'`). The `ImportProcessingWorkflow` Temporal workflow is triggered.

### Step 2: Column Detection
**User action**: Waits briefly.
**System response**: The workflow reads the file headers and applies heuristics to auto-detect column roles:
- Looks for date-like columns ("Date", "Transaction Date", "Txn Date").
- Looks for description columns ("Description", "Narration", "Particulars").
- Looks for amount columns — single signed amount ("Amount") or two-column debit/credit layout ("Debit", "Credit").
- Looks for balance column ("Balance", "Running Balance").
- Recognises the `splitwise_csv` layout if Splitwise-specific headers are present.

`import_jobs.status = 'awaiting_mapping'`. The detected mapping is streamed to the frontend via SSE. `total_rows` is set.

### Step 3: Confirm Column Mapping
**User action**: Reviews the proposed column mapping. If the auto-detection is wrong (e.g., "Particulars" was not recognised as description), the user corrects it by selecting the right target field from a dropdown. See slice `14-confirm-column-mapping.md` for detail. User taps "Confirm mapping".
**System response**: `POST /import/{job_id}/mapping/confirm` sends a `ColumnMappingConfirmed` Temporal signal. `import_column_mappings` rows are saved. Workflow resumes.

### Step 4: Rows Parsed and Categorised
**User action**: Waits while the import processes.
**System response**: Workflow parses all rows using the confirmed mapping:
- For each row: computes fingerprint (`SHA-256(lower(trim(description)) + date.isoformat() + str(abs(amount)))`).
- Checks fingerprint against existing transactions — duplicates are counted in `skipped_rows`.
- Applies categorization rules (rules-only, no AI — bulk processing favours speed over quality).
- Rows with no matching rule are assigned the "Others" category.
- Failed rows (malformed dates, non-numeric amounts) are counted in `failed_rows` with reasons logged in `error_log`.

`import_jobs.status = 'processing'`. Progress updates streamed via SSE.

### Step 5: Batch Published
**User action**: None.
**System response**: `ImportBatchReady` event is published via outbox with all successfully parsed and categorised rows. `transactions` domain consumes this event and creates `transactions` + `transaction_items` records (same idempotency check on fingerprint). `import_jobs.imported_rows` and `skipped_rows` are updated.

### Step 6: Import Completed
**User action**: None.
**System response**: `ImportCompleted` event published. `notifications` domain creates a banner:
- Title: "Import finished"
- Body: "{imported_rows} transactions imported. {skipped_rows} duplicates skipped. {failed_rows} rows could not be imported."
`import_jobs.status = 'completed'`. `completed_at` is set. File is deleted from storage.

## Domains Involved
- **import_**: File storage, column detection, workflow orchestration, batch preparation.
- **categorization**: Rules engine applied in bulk (no AI).
- **transactions**: Creates transaction records from `ImportBatchReady` payload.
- **notifications**: Creates "Import finished" banner.

## Edge Cases & Failures
- **All rows are duplicates**: `imported_rows = 0`, `skipped_rows = total_rows`. The import is still "successful" — re-importing the same file is safe.
- **Splitwise CSV with split amounts**: The dedicated Splitwise parser handles who-paid and who-owes columns. Shared expenses are treated as debits; money received from a split is treated as a credit. Users should review and re-categorize if needed.
- **Large file (1000+ rows)**: Import processes all rows in a single workflow execution. There is no partial-import timeout mechanism equivalent to statement processing — if the workflow fails mid-run, the `import_jobs.status = 'failed'` and no transactions are created (the batch is atomic at the `ImportBatchReady` level).
- **Mixed currencies in the file**: Each row's currency is parsed from the file (or defaults to the user's primary currency if no currency column exists). The `fx` domain handles conversion for any budget/earnings calculations downstream.

## Success Outcome
Historical transactions from the spreadsheet are in the transaction ledger, categorised by rules, with duplicates automatically skipped. Uncategorised rows are in "Others" and can be re-categorised via the transaction edit UI.
