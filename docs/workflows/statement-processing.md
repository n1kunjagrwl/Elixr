# Workflow: StatementProcessingWorkflow

**Domain**: `statements`  
**Trigger**: HTTP upload `POST /statements/upload`  
**Temporal schedule**: Not scheduled — triggered on demand  
**Completion**: Publishes `ExtractionCompleted` event  

---

## Purpose

Converts a raw uploaded file (PDF or CSV bank/credit card statement) into a set of classified, committed transactions. The workflow is durable and human-in-the-loop: it can pause for hours waiting for the user to classify ambiguous transactions, survive server restarts, and resume from exactly the right row.

---

## Step-by-Step Sequence

### Step 1 — Upload received

```
POST /statements/upload
  Body: multipart file + account_id + account_kind

statements service:
  1. Validate file type (pdf or csv) and size (max 20MB)
  2. Store file at uploads/{user_id}/{uuid}.{ext}
  3. Create statement_uploads row (status: 'uploaded')
  4. Create extraction_jobs row (status: 'queued')
  5. Trigger StatementProcessingWorkflow in Temporal
     → store temporal_workflow_id in extraction_jobs
  6. Return {job_id, stream_url} to client
```

### Step 2 — Client opens SSE stream

```
GET /statements/{job_id}/stream
  → Server-Sent Events connection held open
  → Frontend receives events as rows are processed
```

### Step 3 — Parsing activity

```
Activity: parse_statement_file(upload_id)

  If file_type == 'pdf':
    Try pdfplumber first (text-layer extraction, tabular output)
    If pdfplumber yields < 3 rows: fall back to camelot (lattice mode for bordered tables)
    If camelot also fails: mark job failed with error_message

  If file_type == 'csv':
    Use csv.DictReader with auto-dialect detection
    Detect column roles by header keywords:
      date: ['date', 'txn date', 'value date', 'transaction date']
      description: ['description', 'narration', 'particulars', 'details']
      debit: ['debit', 'withdrawal', 'dr']
      credit: ['credit', 'deposit', 'cr']
      balance: ['balance', 'closing balance']

  Output: list of raw row dicts [{date, description, debit, credit, balance}]
  Update extraction_jobs.total_rows = len(rows)
  Update extraction_jobs.status = 'classifying'
  Write all rows to raw_extracted_rows (status: 'pending')
  Delete the uploaded file from storage (file is no longer needed after parsing)

  Set period_start and period_end on statement_uploads:
    period_start = min(row.date for row in rows)
    period_end   = max(row.date for row in rows)

  Check for date-range overlap with prior completed/partial uploads for this account:
    SELECT id, period_start, period_end FROM statement_uploads
    WHERE account_id = :account_id AND status IN ('completed', 'partial')
      AND period_start <= :period_end AND period_end >= :period_start
    If overlap found:
      → Emit SSE warning: { type: 'overlap_warning', existing_start, existing_end }
      → Continue processing — overlap is informational only
```

### Step 4 — Classification loop (per row)

For each row in the extracted list:

```
Activity: classify_row(row_id, user_id)

  1. Rules check (synchronous, no ADK):
     Call categorization.suggest_category(description, user_id)
     If source == 'rule' (confidence = 1.0):
       → Mark raw_extracted_rows.classification_status = 'auto_classified'
       → Set ai_suggested_category_id, ai_confidence = 1.0
       → Emit SSE event: {row_id, status: 'auto_classified', category_id, confidence: 1.0}
       → Continue to next row

  2. ADK agent classification:
     Call ADK agent with:
       - description, amount, date
       - categories_for_user (from categorization SQL view)
       - last 5 similar transactions for context (from transactions_with_categories view)
       - prior classifications in this job session (for consistency)

     ADK agent may use tools:
       - get_user_categories(user_id) → categories list
       - get_similar_transactions(description, user_id) → recent matches

     ADK returns: {category_id, confidence, item_suggestions: [string]}

  3. If confidence >= 0.85:
     → Mark classification_status = 'auto_classified'
     → Emit SSE event: {row_id, status: 'auto_classified', category_id, confidence, item_suggestions}
     → Continue to next row

  4. If confidence < 0.85:
     → Mark classification_status = 'pending'
     → Update extraction_jobs.status = 'awaiting_input'
     → Emit SSE event: {row_id, status: 'needs_classification', ai_suggestion: {category_id, confidence}}
     → workflow.wait_for_signal('ClassificationSubmitted', row_id=row_id)
     ← Signal received from: POST /statements/{job_id}/rows/{row_id}/classify

  5. On signal received:
     payload: {category_id, items: [{label, amount}] | null}
     → Update raw_extracted_rows:
          final_category_id = category_id
          final_items = items or [{label: null, amount: row.debit or row.credit}]
          classification_status = 'user_classified'
     → Emit SSE event: {row_id, status: 'classified'}
     → Update extraction_jobs.classified_rows += 1
```

### Step 5 — Completion

```
After all rows are classified:

  1. Build classified_rows payload:
     For each raw_extracted_row with final_category_id set:
       {
         date, description, amount, currency,
         type: 'debit' if debit_amount else 'credit',
         category_id: final_category_id,
         items: final_items
       }

  2. Publish ExtractionCompleted event (via outbox):
     {job_id, upload_id, user_id, account_id, account_kind, classified_rows}

  3. Update extraction_jobs.status = 'completed', completed_at = now()
  4. Update statement_uploads.status = 'completed'
  5. Close SSE stream
```

### Step 6 — Transaction creation (transactions domain)

The `transactions` domain handles the `ExtractionCompleted` event:

```
For each row in classified_rows:
  1. Compute fingerprint = SHA-256(lower(trim(description)) + date + str(amount))
  2. If fingerprint already exists for this user: skip (duplicate)
  3. Create transactions row
  4. Create transaction_items rows (one per item, or one unlabelled row if no items)
  5. Publish TransactionCreated event
  6. Publish TransactionCategorized event
```

---

## Error Handling

| Failure point | Behaviour |
|---|---|
| File cannot be parsed | Mark job `failed`, notify user via SSE |
| ADK agent timeout | Treat as low-confidence → ask user |
| ADK returns no category | Treat as low-confidence → ask user |
| User never classifies a row | Workflow times out after 7 days. All classified rows (auto + user-confirmed) are committed by publishing `ExtractionPartiallyCompleted`. Unclassified rows are marked `skipped`. `extraction_jobs.status` and `statement_uploads.status` are set to `partial`. A notification is created listing the discarded date range — the user can re-upload; fingerprint deduplication will skip already-committed rows and only process the discarded ones. |
| Server restart mid-workflow | Temporal replays from the last durable checkpoint; already-classified rows are not re-processed |

---

## SSE Event Schema

```json
{
  "event": "row_update",
  "data": {
    "row_id": "uuid",
    "row_index": 42,
    "date": "2026-03-15",
    "description": "SWIGGY ORDER",
    "amount": 450.00,
    "type": "debit",
    "status": "auto_classified | needs_classification | classified | skipped",
    "ai_suggestion": {
      "category_id": "uuid",
      "category_name": "Food & Dining",
      "confidence": 0.92,
      "item_suggestions": ["Food delivery", "Delivery fee"]
    }
  }
}
```

```json
{
  "event": "job_completed",
  "data": {
    "job_id": "uuid",
    "total_rows": 187,
    "classified_rows": 187,
    "skipped_rows": 0
  }
}
```
