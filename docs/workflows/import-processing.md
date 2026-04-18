# Workflow: ImportProcessingWorkflow

**Domain**: `import_`  
**Trigger**: HTTP upload `POST /import/upload`  
**Temporal schedule**: Not scheduled — triggered on demand  

---

## Purpose

Imports bulk historical transaction data from a generic CSV or spreadsheet (XLSX) into Elixir. Unlike statement processing, the column layout is unknown in advance. The workflow auto-detects columns, presents the mapping to the user for confirmation, then processes the rows using categorisation rules in bulk. This is designed for users who have been tracking expenses in a spreadsheet and want to bring their history into Elixir.

---

## Step-by-step

### Step 1 — Upload received

```
POST /import/upload
  Body: multipart file + optional source_type hint

import_ service:
  1. Validate file type (csv or xlsx) and size (max 50MB)
  2. Store file at imports/{user_id}/{uuid}.{ext}
  3. Create import_jobs row (status: 'uploaded')
  4. Trigger ImportProcessingWorkflow in Temporal
  5. Return { job_id, stream_url }
```

### Step 2 — Column detection activity

```
Activity: detect_columns(job_id)

  Read file:
    CSV:  csv.DictReader with auto-dialect (comma, semicolon, tab)
    XLSX: openpyxl, read first sheet

  Extract header row (first non-empty row).

  For each column header, score against known keywords:
    date:          ['date', 'txn date', 'transaction date', 'value date', 'posting date']
    description:   ['description', 'narration', 'particulars', 'merchant', 'details', 'note']
    debit_amount:  ['debit', 'dr', 'withdrawal', 'amount debited']
    credit_amount: ['credit', 'cr', 'deposit', 'amount credited']
    amount:        ['amount', 'net amount']  -- signed, positive=credit
    balance:       ['balance', 'closing balance', 'available balance']
    category:      ['category', 'type', 'tag']
    ignore:        anything not matched above

  Detect special source types by header fingerprint:
    Splitwise CSV: headers include 'Currency', 'Cost', 'Owed by you', 'Owed to you'
    → Use dedicated Splitwise parser instead of generic mapping

  Store detected mapping in import_column_mappings.
  Emit SSE event: { status: 'awaiting_mapping', detected_columns: [...], sample_rows: first 3 rows }
  Update import_jobs.status = 'awaiting_mapping'
  workflow.wait_for_signal('ColumnMappingConfirmed')
```

### Step 3 — User confirms mapping

```
POST /import/{job_id}/confirm-mapping
  Body: { column_mappings: [{source_column, mapped_to}, ...] }

  → Update import_column_mappings rows with user's confirmed mapping
  → Send Temporal signal: ColumnMappingConfirmed
```

### Step 4 — Row processing activity

```
Activity: process_rows(job_id)

  Update import_jobs.status = 'processing'

  Read all rows using confirmed mapping.

  For each row:

  1. Parse date:
     Try multiple formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD MMM YYYY
     If unparseable: log to error_log, skip row, increment failed_rows

  2. Determine amount and type:
     If mapped_to contains 'debit_amount' and 'credit_amount':
       type = 'debit' if debit_col has value else 'credit'
       amount = abs(debit_col or credit_col)
     If mapped_to contains 'amount' (signed):
       amount = abs(row.amount)
       type = 'credit' if row.amount > 0 else 'debit'

  3. Compute fingerprint:
     SHA-256(lower(trim(description)) + date.isoformat() + str(amount))

  4. Deduplication check:
     SELECT 1 FROM transactions WHERE user_id = ? AND fingerprint = ?
     → If exists: skip, increment skipped_rows, continue

  5. Category resolution:
     If file had a 'category' column and user mapped it:
       Try to match the file's category name to categories_for_user by slug or exact name
       If matched: use as category_id
       If not matched: default to 'Others'

     If no category column:
       Apply categorization_rules for this user (same as statement processing rules step)
       If no rule matches: category = 'Others'

  6. Create transaction (call transactions.service.create):
     source = 'bulk_import'
     Emit TransactionCreated event

  7. Create transaction_items (one row, category as resolved above, label = NULL)
     Emit TransactionCategorized event

  8. Increment import_jobs.imported_rows

  9. Emit SSE progress event every 50 rows:
     { status: 'processing', imported: N, total: M, skipped: K }
```

### Step 5 — Completion

```
  Update import_jobs.status = 'completed', completed_at = now()
  Publish ImportCompleted event (via outbox)
  Emit SSE event: { status: 'completed', imported_rows, skipped_rows, failed_rows, error_log }
```

---

## SSE Events

```json
{ "event": "mapping_detected", "data": {
    "job_id": "uuid",
    "detected": [{"source_column": "Date", "mapped_to": "date"}, ...],
    "sample": [{"Date": "01/04/2026", "Narration": "SWIGGY", "Debit": "450"}, ...]
}}

{ "event": "progress", "data": {
    "imported": 150, "total": 500, "skipped": 12, "failed": 2
}}

{ "event": "completed", "data": {
    "imported_rows": 482, "skipped_rows": 16, "failed_rows": 2,
    "error_log": [{"row": 47, "reason": "unparseable date: '32/13/2025'"}]
}}
```

---

## Error Handling

| Failure | Behaviour |
|---|---|
| File cannot be read | Mark job `failed`, notify via SSE |
| Row date unparseable | Skip row, add to `error_log`, continue |
| Row amount invalid | Skip row, add to `error_log`, continue |
| Transaction create fails | Skip row, add to `error_log`, continue |
| User never confirms mapping | Workflow times out after 24 hours; job marked `failed`; file deleted |

Partial success is acceptable — the import reports exactly how many rows succeeded, were skipped (duplicates), or failed (parse errors). The user can fix their file and re-upload; duplicates are automatically skipped.

---

## Idempotency

The entire workflow is safe to re-run. Deduplication via fingerprint ensures re-uploading the same file has no effect on existing transactions. The `import_jobs` table captures the result of every attempt separately.
