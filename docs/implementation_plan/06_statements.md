# Implementation Plan: statements

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/statements.md`](../domains/statements.md)
- Data model: [`docs/data-model.md`](../data-model.md#statements)
- Workflow: [`docs/workflows/statement-processing.md`](../workflows/statement-processing.md)
- User slices: 09-upload-bank-statement, 10-classify-low-confidence-rows, 11-resume-abandoned-statement, 12-reupload-partial-statement

## Dependencies
- `identity` — JWT auth middleware
- `accounts` — `user_accounts_summary` view (validates account belongs to user; resolves display name)
- `categorization` — `suggest_category()` service method (Pattern 3, called inside Temporal activity)
- `transactions` — subscribes to `ExtractionCompleted` / `ExtractionPartiallyCompleted` (statements publishes; transactions consumes)

`categorization` must be seeded with default categories before the first statement is processed.

## What to Build
The staging pipeline between a file upload and committed transactions. Stores uploaded files, runs a durable Temporal workflow (`StatementProcessingWorkflow`) that parses the file, calls the ADK agent row-by-row, pauses for low-confidence rows, and streams results to the frontend via SSE. Raw extracted rows live in this domain until the user classifies them; then `ExtractionCompleted` triggers the `transactions` domain to take ownership.

## Tables to Create
| Table | Key columns |
|---|---|
| `statement_uploads` | `user_id`, `account_id`, `account_kind`, `file_path`, `file_type`, `original_filename`, `period_start`, `period_end`, `status`, `uploaded_at` |
| `extraction_jobs` | `upload_id` FK→`statement_uploads.id`, `temporal_workflow_id`, `status`, `total_rows`, `classified_rows`, `error_message`, `completed_at` |
| `raw_extracted_rows` | `job_id` FK→`extraction_jobs.id`, `row_index`, `date`, `description`, `debit_amount`, `credit_amount`, `balance`, `classification_status`, `ai_suggested_category_id`, `ai_confidence`, `final_category_id`, `transaction_id` |
| `raw_row_items` | `row_id` FK→`raw_extracted_rows.id`, `label`, `amount` |
| `statements_outbox` | standard outbox schema |

Note: `raw_row_items` replaces any JSONB item column — item amounts must sum to the row's debit/credit amount (enforced in service layer, not DB).

`status` enum for `statement_uploads`: `uploaded | processing | completed | partial | failed`
`status` enum for `extraction_jobs`: `queued | parsing | classifying | awaiting_input | completed | partial | failed`
`classification_status` enum for `raw_extracted_rows`: `pending | auto_classified | user_classified | skipped`

## Events Published
| Event | Consumed by |
|---|---|
| `statements.StatementUploaded` | Audit only |
| `statements.ExtractionCompleted` | `transactions`, `notifications` |
| `statements.ExtractionPartiallyCompleted` | `transactions`, `notifications` |

## Events Subscribed
None — statements is triggered by HTTP upload, not by domain events.

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/statements/upload` | Upload a PDF or CSV statement file |
| `GET` | `/statements` | List statement uploads for the user |
| `GET` | `/statements/{upload_id}` | Get upload status and extraction job details |
| `GET` | `/statements/{job_id}/stream` | SSE stream of classified rows as they arrive |
| `POST` | `/statements/{job_id}/rows/{row_id}/classify` | Submit user classification for a pending row (sends Temporal signal) |
| `GET` | `/statements/{job_id}/rows` | List all raw extracted rows for a job (for resume UI) |

## Action Steps

### Step 1 — Create `models.py`
Define `StatementUpload`, `ExtractionJob`, `RawExtractedRow`, `RawRowItem`, and `StatementsOutbox`.
- `StatementUpload`: `Base`, `IDMixin`, `TimestampMixin` (use `uploaded_at` not standard `created_at` — add an alias or override)
- `ExtractionJob`: FK to `StatementUpload` (within-domain PG FK)
- `RawExtractedRow`: FK to `ExtractionJob` (within-domain PG FK); `ai_suggested_category_id` and `final_category_id` are `uuid | None` (no PG FK — cross-domain references)
- `RawRowItem`: FK to `RawExtractedRow` (within-domain PG FK)
- `account_kind`: `CheckConstraint` for `bank | credit_card`
- `file_type`: `CheckConstraint` for `pdf | csv`

### Step 2 — Create Alembic migration
`uv run alembic revision --autogenerate -m "statements: add statement_uploads, extraction_jobs, raw_extracted_rows, raw_row_items, statements_outbox"`.
Confirm all FKs, check constraints, and nullable columns are correct.

### Step 3 — Create `repositories.py`
Key methods:
- `create_upload(user_id, account_id, account_kind, file_path, file_type, original_filename) -> StatementUpload`
- `get_upload(user_id, upload_id) -> StatementUpload | None`
- `list_uploads(user_id) -> list[StatementUpload]`
- `update_upload_status(upload, status, period_start?, period_end?) -> None`
- `create_extraction_job(upload_id, temporal_workflow_id?) -> ExtractionJob`
- `get_job(job_id) -> ExtractionJob | None`
- `update_job_status(job, status, total_rows?, classified_rows?, error_message?) -> None`
- `create_raw_rows(job_id, rows: list[dict]) -> list[RawExtractedRow]` — bulk insert
- `get_raw_row(row_id) -> RawExtractedRow | None`
- `update_raw_row_classification(row, classification_status, final_category_id?, transaction_id?) -> None`
- `create_raw_row_items(row_id, items: list[dict]) -> None`
- `list_raw_rows(job_id) -> list[RawExtractedRow]`
- `check_date_range_overlap(user_id, account_id, period_start, period_end) -> bool` — checks prior completed/partial uploads for the same account

### Step 4 — Create `services.py`
- `upload_statement(user_id, account_id, account_kind, file, file_type, original_filename, storage_client, temporal_client) -> StatementUpload`
  - Save file to user-scoped path via `storage_client`
  - Create `StatementUpload` and `ExtractionJob` rows
  - Write `StatementUploaded` to outbox in same transaction
  - Start `StatementProcessingWorkflow` in Temporal (fire-and-forget)
- `get_upload_status(user_id, upload_id) -> UploadStatusResponse`
- `list_uploads(user_id) -> list[UploadResponse]`
- `classify_row(user_id, job_id, row_id, category_id, items: list[dict], temporal_client) -> None`
  - Validate row belongs to this user's job
  - Send Temporal signal `RowClassified` to the workflow
  - Update `raw_extracted_rows.classification_status = 'user_classified'` and `final_category_id`
  - If items provided: validate amounts sum to row's debit/credit amount; insert `raw_row_items`
- `get_rows_for_resume(user_id, job_id) -> list[RawRowResponse]` — returns rows for the resume UI

### Step 5 — Create `schemas.py`
- `UploadResponse` — upload_id, account_id, account_kind, file_type, status, uploaded_at, period_start, period_end
- `ExtractionJobResponse` — job_id, upload_id, status, total_rows, classified_rows, temporal_workflow_id
- `UploadStatusResponse` — combines upload + job
- `RawRowResponse` — id, row_index, date, description, debit_amount, credit_amount, balance, classification_status, ai_suggested_category_id, ai_confidence, final_category_id
- `ClassifyRowRequest` — category_id (UUID), items (optional list of `{label, amount}`)
- `SSERowEvent` — row_id, row_index, description, amount, currency, type, classification_status, needs_classification (bool), ai_suggested_category_id, ai_confidence

### Step 6 — Create Temporal workflow `workflows/statement_processing.py`
```
StatementProcessingWorkflow.run(upload_id, job_id, user_id, account_id, account_kind, file_path, file_type):
  1. Activity: parse_file(file_path, file_type) → list[raw_rows]
     - pdfplumber for text-layer PDFs; camelot for table-heavy PDFs; csv.DictReader for CSVs
     - Store raw rows in DB; update job total_rows; set upload period_start and period_end
  2. Activity: check_date_overlap(user_id, account_id, period_start, period_end)
     - If overlap: emit SSE warning (not a workflow error — processing continues)
  3. For each raw_row:
     a. Activity: call categorization.suggest_category(description, user_id, amount) → CategorySuggestion
     b. If confidence >= 0.85 or source == 'rule':
        - Mark row auto_classified; SSE event to frontend
        - Increment job.classified_rows
     c. If confidence < 0.85:
        - SSE event with needs_classification=true
        - await workflow.wait_condition(lambda: row has been classified) OR timeout
        - On signal RowClassified: mark user_classified; increment job.classified_rows
  4. On all rows classified:
     - Publish ExtractionCompleted to outbox (with classified_rows payload)
     - Update job.status = 'completed', upload.status = 'completed'
     - Delete file from storage (only raw extracted rows are retained)
  5. On 7-day timeout:
     - Publish ExtractionPartiallyCompleted (classified_rows only) to outbox
     - Mark unclassified rows as 'skipped'
     - Update job.status = 'partial', upload.status = 'partial'
```

**Key constraint**: Temporal workflows must be deterministic. All side effects (DB writes, API calls, file I/O) must be inside `@activity.defn` functions.

### Step 7 — Create Temporal activities `workflows/activities.py`
- `parse_pdf_activity(file_path) -> list[dict]` — pdfplumber or camelot
- `parse_csv_activity(file_path) -> list[dict]`
- `store_raw_rows_activity(job_id, rows) -> None`
- `classify_row_activity(job_id, row_id, user_id, description, amount) -> CategorySuggestion`
  - Calls `categorization.suggest_category()` — injected as a dependency
- `publish_extraction_completed_activity(job_id, upload_id, user_id, classified_rows) -> None`
- `delete_file_activity(file_path) -> None`

### Step 8 — Implement SSE streaming in `api.py`
The `GET /statements/{job_id}/stream` endpoint returns `EventSourceResponse` (using `sse-starlette` or equivalent). The workflow pushes SSE events by writing to a shared in-memory queue keyed by `job_id`. The SSE handler yields from this queue.

### Step 9 — Create `events.py`
```python
@dataclass
class StatementUploaded:
    event_type: ClassVar[str] = "statements.StatementUploaded"
    upload_id: UUID; user_id: UUID; account_id: UUID; file_type: str

@dataclass
class ExtractionCompleted:
    event_type: ClassVar[str] = "statements.ExtractionCompleted"
    job_id: UUID; upload_id: UUID; user_id: UUID; account_id: UUID; account_kind: str
    classified_rows: list[dict]  # [{date, description, amount, currency, type, category_id, items}]

@dataclass
class ExtractionPartiallyCompleted:
    event_type: ClassVar[str] = "statements.ExtractionPartiallyCompleted"
    job_id: UUID; upload_id: UUID; user_id: UUID; account_id: UUID; account_kind: str
    classified_rows: list[dict]
    discarded_from_date: date; discarded_to_date: date
```

No event handlers — `statements` does not subscribe to any events.

### Step 10 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    event_bus.register_outbox_table("statements_outbox")

def get_temporal_workflows() -> list:
    from elixir.domains.statements.workflows.statement_processing import StatementProcessingWorkflow
    return [StatementProcessingWorkflow]

def get_temporal_activities(categorization_service, storage_client, session_factory) -> list:
    from elixir.domains.statements.workflows.activities import StatementActivities
    a = StatementActivities(categorization_service=categorization_service, storage_client=storage_client, session_factory=session_factory)
    return [a.parse_pdf, a.parse_csv, a.store_raw_rows, a.classify_row, a.publish_extraction_completed, a.delete_file]
```

### Step 11 — Register router in `runtime/app.py`
Include `statements` router under prefix `/statements`.

## Verification Checklist
- [ ] PDF upload → Temporal workflow starts → rows stream to client via SSE
- [ ] Low-confidence row pauses workflow; `waitForSignal` resumes on `classify_row` call
- [ ] 7-day workflow timeout publishes `ExtractionPartiallyCompleted` (not `ExtractionCompleted`)
- [ ] Date-range overlap emits SSE warning but does not block processing
- [ ] File is deleted from storage after parsing completes (only extracted rows retained)
- [ ] `ExtractionCompleted` and `ExtractionPartiallyCompleted` are written to outbox atomically
- [ ] `raw_row_items` amounts sum to row's debit/credit amount — service rejects mismatches
- [ ] Ruff + mypy pass with no errors
