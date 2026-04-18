# Domain: statements

## Responsibility

Handles everything between a file upload and a committed transaction. When a user uploads a bank or credit card statement (PDF or CSV), this domain stores the file, triggers a durable Temporal processing workflow, tracks extraction progress, and streams results to the frontend. It acts as the staging layer — raw extracted rows live here until the user classifies them, at which point the `transactions` domain takes ownership.

The statements domain deliberately holds extracted rows in a staging state before they become transactions. This means a user can abandon the classification mid-way, resume later, and their progress is preserved because Temporal holds the workflow state durably.

---

## Tables Owned

### `statement_uploads`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `account_id` | `uuid` NOT NULL | → `accounts.bank_accounts.id` or `credit_cards.id` (no PG FK) |
| `account_kind` | `text` NOT NULL | `bank` \| `credit_card` |
| `file_path` | `text` NOT NULL | User-scoped path on file storage, e.g. `uploads/{user_id}/{uuid}.pdf` |
| `file_type` | `text` NOT NULL | `pdf` \| `csv` |
| `original_filename` | `text` | Original name as uploaded (for display) |
| `status` | `text` NOT NULL DEFAULT `'uploaded'` | `uploaded` \| `processing` \| `completed` \| `failed` |
| `uploaded_at` | `timestamptz` | — |

### `extraction_jobs`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `upload_id` | `uuid` FK → `statement_uploads.id` | — |
| `temporal_workflow_id` | `text` | Temporal workflow run ID, for sending signals |
| `status` | `text` NOT NULL DEFAULT `'queued'` | `queued` \| `parsing` \| `classifying` \| `awaiting_input` \| `completed` \| `failed` |
| `total_rows` | `int` | Set after parsing completes |
| `classified_rows` | `int` DEFAULT 0 | Incremented as rows are classified |
| `error_message` | `text` | Populated if status = `failed` |
| `created_at` | `timestamptz` | — |
| `completed_at` | `timestamptz` | — |

### `raw_extracted_rows`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `job_id` | `uuid` FK → `extraction_jobs.id` | — |
| `row_index` | `int` NOT NULL | Original position in the statement (for ordering) |
| `date` | `date` | Transaction date parsed from statement |
| `description` | `text` | Raw description from statement |
| `debit_amount` | `numeric(15,2)` | Null if credit row |
| `credit_amount` | `numeric(15,2)` | Null if debit row |
| `balance` | `numeric(15,2)` | Running balance from statement (if available) |
| `classification_status` | `text` DEFAULT `'pending'` | `pending` \| `auto_classified` \| `user_classified` \| `skipped` |
| `ai_suggested_category_id` | `uuid` | ADK agent's suggestion (no PG FK to categories) |
| `ai_confidence` | `float` | 0.0–1.0 |
| `final_category_id` | `uuid` | Set on user confirmation |
| `final_items` | `jsonb` | `[{label, amount}]` if user provides item breakdown |
| `transaction_id` | `uuid` | Set when the row is committed as a transaction |

### `outbox`
Standard outbox table. See [data-model.md](../data-model.md).

---

## SQL Views Exposed

None. Other domains do not need to read raw extracted rows.

---

## Events Published

### `StatementUploaded`
```python
@dataclass
class StatementUploaded:
    event_type = "statements.StatementUploaded"
    upload_id: UUID
    user_id: UUID
    account_id: UUID
    file_type: str
```

### `ExtractionCompleted`
```python
@dataclass
class ExtractionCompleted:
    event_type = "statements.ExtractionCompleted"
    job_id: UUID
    upload_id: UUID
    user_id: UUID
    account_id: UUID
    account_kind: str
    classified_rows: list[dict]  # [{date, description, amount, currency, type, category_id, items}]
```
Consumed by: `transactions` (creates transaction records from `classified_rows`)

---

## Events Subscribed

None. The statements domain is triggered by an HTTP upload, not by domain events.

---

## Temporal Workflow

### `StatementProcessingWorkflow`

See [workflows/statement-processing.md](../workflows/statement-processing.md) for the full step-by-step sequence.

Summary:
1. Parse the uploaded file (pdfplumber or camelot for PDF; csv.DictReader for CSV)
2. For each extracted row: call ADK agent for classification
3. High-confidence rows (≥0.85): mark as `auto_classified`, stream to frontend
4. Low-confidence rows: mark `pending`, stream with `needs_classification: true`, pause workflow via `waitForSignal`
5. User submits classification → Temporal signal → workflow resumes
6. On all rows classified: publish `ExtractionCompleted`, update `extraction_jobs.status = 'completed'`

---

## Key Design Decisions

**Raw rows stored before any transaction is created.** This staging layer gives the user the ability to review, edit, and abandon classification without corrupting the transaction ledger. A transaction is only created after the user confirms the classification.

**Temporal `waitForSignal` for human-in-the-loop.** Pausing the workflow mid-statement allows the server to restart, the user to close the browser, and the classification to resume from exactly where it left off. This would be impossible with a traditional queue-based approach.

**SSE for streaming row-by-row results.** Rather than waiting for the entire statement to process before showing anything, the frontend receives rows as they are classified. For a 200-transaction statement this makes the experience feel interactive rather than batch-like.

**`temporal_workflow_id` stored in `extraction_jobs`.** The FastAPI signal endpoint (`POST /statements/{job_id}/rows/{row_id}/classify`) uses this ID to send a Temporal signal directly to the correct workflow run. No polling needed.
