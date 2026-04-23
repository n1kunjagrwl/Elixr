# Slice: Confirm Column Mapping During Import

## User Goal
Tell Elixir which column in the uploaded CSV/XLSX corresponds to which transaction field so the import can parse correctly.

## Trigger
The `ImportProcessingWorkflow` has auto-detected columns and paused at `waitForSignal(ColumnMappingConfirmed)`. The frontend shows the mapping confirmation UI.

## Preconditions
- An `import_jobs` row exists with `status = 'awaiting_mapping'`.
- The file header row has been parsed and column names are known.

## Steps

### Step 1: Review Auto-Detected Mapping
**User action**: None — the UI presents the auto-detected mapping.
**System response**: Each source column from the file (e.g., "Txn Date", "Particulars", "Debit Amount", "Credit Amount", "Balance") is shown alongside Elixir's proposed mapping target:
- `date` — transaction date
- `description` — raw description
- `debit_amount` — negative/outflow amount
- `credit_amount` — positive/inflow amount
- `amount` — signed single-column amount (positive = credit, negative = debit)
- `balance` — running balance (informational, not required)
- `category` — if the file has a category column
- `ignore` — columns Elixir should not process

A sample of the first 5 rows is shown so the user can verify the mapping makes sense.

### Step 2: Correct Any Wrong Mappings
**User action**: If "Narration" was not auto-detected as description, user opens the dropdown next to "Narration" and selects `description`.
**System response**: Frontend updates the proposed mapping in state. Required fields validated: at least `date`, `description`, and at least one of `amount` / `debit_amount` / `credit_amount` must be mapped. The "Confirm" button is enabled only when required fields are covered.

### Step 3: Handle Amount Layout
**User action**: If the file uses a single signed amount column, user maps it to `amount`. If separate debit/credit columns exist, maps each to `debit_amount` / `credit_amount` respectively.
**System response**: The import parser will use the mapped layout: signed `amount` → positive = credit, negative = debit. Two-column layout → debit_amount rows get `type='debit'`, credit_amount rows get `type='credit'`.

### Step 4: Confirm Mapping
**User action**: Taps "Confirm mapping".
**System response**: `POST /import/{job_id}/mapping/confirm` is called with the confirmed mapping array. `import_column_mappings` rows are inserted — one per source column. The `ColumnMappingConfirmed` Temporal signal is sent with the mapping payload. The workflow resumes from `waitForSignal` and proceeds to parse all rows. `import_jobs.status = 'processing'`.

## Domains Involved
- **import_**: Owns column mapping storage and Temporal signal endpoint.

## Edge Cases & Failures
- **Required field not mapped**: The "Confirm" button is disabled. User must map at least date, description, and an amount field before confirming.
- **Two columns both mapped to `description`**: The import parser concatenates them (e.g., "HDFC NEFT - Reference 123456" from two columns). This is an edge case but acceptable.
- **File has no header row**: The auto-detection fails (no meaningful column names). User must manually assign all mappings using column letters (A, B, C) instead of names.
- **User confirms an incorrect mapping and import produces wrong data**: The import will create transactions with wrong dates or amounts. The user must delete the import batch manually (if this feature exists) or edit each transaction. Prevention: the sample row preview in Step 1 shows exactly how the first 5 rows will be parsed.

## Success Outcome
Column mappings are saved and the workflow resumes. All rows in the file are parsed using the confirmed column layout.
