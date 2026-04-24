# Implementation Plan: import_

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/import_.md`](../domains/import_.md)
- Data model: [`docs/data-model.md`](../data-model.md#import_)
- Workflow: [`docs/workflows/import-processing.md`](../workflows/import-processing.md)
- User slices: 13-import-csv-bulk, 14-confirm-column-mapping, 43-delete-import-batch

## Dependencies
- `identity` — JWT auth middleware
- `categorization` — rules engine (applied in bulk during import; no ADK calls)
- `transactions` — subscribes to `ImportBatchReady`; `transactions` must be registered before `import_` publishes

## What to Build
Bulk import of historical transaction data from generic CSV/XLSX files or named formats (e.g., Splitwise CSV). Unlike `statements`, which processes bank-formatted PDFs/CSVs, `import_` handles arbitrary user data with unknown column layouts. Column mapping is confirmed by the user via a Temporal signal (human-in-the-loop). Categorisation is rules-only — no ADK agent — to handle potentially thousands of historical rows efficiently.

## Tables to Create
| Table | Key columns |
|---|---|
| `import_jobs` | `user_id`, `file_path`, `original_filename`, `source_type`, `temporal_workflow_id`, `status`, `total_rows`, `imported_rows`, `skipped_rows`, `failed_rows`, `completed_at` |
| `import_column_mappings` | `job_id` FK→`import_jobs.id`, `source_column`, `mapped_to` |
| `import_row_errors` | `job_id` FK→`import_jobs.id`, `row_index`, `reason` |
| `import_outbox` | standard outbox schema |

`status` enum for `import_jobs`: `uploaded | awaiting_mapping | processing | completed | failed`

`mapped_to` enum for `import_column_mappings`: `date | description | debit_amount | credit_amount | amount | balance | category | ignore`

Note: `import_row_errors` replaces any JSONB error log column — one row per failed row in the uploaded file.

## Events Published
| Event | Consumed by |
|---|---|
| `import_.ImportBatchReady` | `transactions` — creates transaction records |
| `import_.ImportCompleted` | `notifications` — "Import finished" banner |

## Events Subscribed
None — import is triggered by HTTP file upload.

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `POST` | `/import/upload` | Upload a CSV or XLSX file |
| `GET` | `/import/{job_id}` | Get job status and progress |
| `GET` | `/import/{job_id}/stream` | SSE stream for column mapping preview and import progress |
| `POST` | `/import/{job_id}/confirm-mapping` | Confirm/correct column mapping (sends Temporal signal) |
| `DELETE` | `/import/{job_id}` | Delete an import batch and its data |

## Action Steps

### Step 1 — Create `models.py`
Define `ImportJob`, `ImportColumnMapping`, `ImportRowError`, and `ImportOutbox`.
- `ImportJob`: `Base`, `IDMixin`, `TimestampMixin` (no `updated_at` — track progress via `status` and counters)
- `source_type`: `CheckConstraint` for `csv_generic | xlsx_generic | splitwise_csv`
- `status`: `CheckConstraint` for `uploaded | awaiting_mapping | processing | completed | failed`
- `ImportColumnMapping`: FK to `ImportJob`; immutable (no `updated_at`)
- `ImportRowError`: FK to `ImportJob`; immutable (append-only)
- `mapped_to`: `CheckConstraint` for the 8 mapping targets

### Step 2 — Create Alembic migration
`uv run alembic revision --autogenerate -m "import_: add import_jobs, import_column_mappings, import_row_errors, import_outbox"`.

### Step 3 — Create `repositories.py`
Key methods:
- `create_job(user_id, file_path, original_filename, source_type) -> ImportJob`
- `get_job(user_id, job_id) -> ImportJob | None`
- `update_job(job, **fields) -> ImportJob` — status, temporal_workflow_id, total_rows, counters, completed_at
- `create_column_mappings(job_id, mappings: list[dict]) -> None` — bulk insert
- `get_column_mappings(job_id) -> list[ImportColumnMapping]`
- `create_row_errors(job_id, errors: list[dict]) -> None` — bulk insert
- `list_jobs(user_id) -> list[ImportJob]`
- `delete_job(job) -> None` — cascades to mappings and errors via DB FK

### Step 4 — Create `schemas.py`
- `ImportJobResponse` — id, source_type, status, total_rows, imported_rows, skipped_rows, failed_rows, created_at, completed_at
- `ColumnMappingPreview` — detected column headers with suggested mappings
- `ColumnMappingConfirmRequest` — list of `{source_column, mapped_to}`
- `ImportRowErrorResponse` — row_index, reason
- `SSEMappingEvent` — event sent to client with auto-detected column mapping for review

### Step 5 — Create `services.py`
- `upload_file(user_id, file, source_type, original_filename, storage_client, temporal_client) -> ImportJobResponse`
  - Save file to user-scoped path
  - Create `ImportJob` row
  - Start `ImportProcessingWorkflow` in Temporal
- `get_job_status(user_id, job_id) -> ImportJobResponse`
- `confirm_mapping(user_id, job_id, mappings: list[dict], temporal_client) -> None`
  - Validate all `mapped_to` values are valid
  - Validate required fields are mapped (`date`, `description`, and at least one amount column)
  - Store `ImportColumnMapping` rows
  - Send Temporal signal `ColumnMappingConfirmed` to the workflow
- `delete_import(user_id, job_id, storage_client) -> None`
  - Only allowed for `completed` or `failed` jobs
  - Delete file from storage, then delete DB rows (cascade)
  - Note: transactions already created are NOT deleted — they belong to the `transactions` domain

### Step 6 — Create Temporal workflow `workflows/import_processing.py`
```
ImportProcessingWorkflow.run(job_id, user_id, file_path, source_type):
  1. Activity: detect_columns(file_path, source_type)
     - Read file headers; apply heuristics for common names (Date, Amount, Description, etc.)
     - Emit SSE event with suggested column mapping
     - Update job.status = 'awaiting_mapping'
  2. await workflow.wait_condition(ColumnMappingConfirmed signal received) — up to 7 days
  3. Activity: parse_all_rows(file_path, confirmed_mappings) → (valid_rows, error_rows)
     - For each row: parse date, description, amounts; compute fingerprint
     - Collect errors for unparseable rows
  4. Activity: apply_categorization_rules(valid_rows, user_id)
     - For each row: check categorization_rules (no ADK); assign category_id or default to 'Others'
  5. Activity: store_import_stats(job_id, total, valid_count, error_rows) → ImportJob
     - Insert import_row_errors for failed rows
     - Update job.total_rows, job.failed_rows
  6. Activity: publish_import_batch_ready(job_id, user_id, valid_rows) via outbox
     - valid_rows format: [{date, description, amount, currency, type, category_id, source='bulk_import'}]
  7. Activity: publish_import_completed(job_id, user_id, imported_rows, skipped_rows, failed_rows) via outbox
     - Note: imported_rows = valid_rows count submitted; actual transactions created may be lower due to dedup
  8. Update job.status = 'completed', job.completed_at = now()
```

### Step 7 — Create Temporal activities `workflows/activities.py`
- `detect_columns_activity(file_path, source_type) -> list[dict]` — returns `[{source_column, suggested_mapped_to}]`
- `parse_rows_activity(file_path, mappings) -> tuple[list[dict], list[dict]]` — valid rows + error rows
- `apply_rules_activity(rows, user_id, session_factory) -> list[dict]` — returns rows with `category_id` set
- `store_errors_activity(job_id, error_rows, session_factory) -> None`
- `publish_batch_ready_activity(job_id, user_id, rows, session_factory) -> None`
- `publish_completed_activity(job_id, user_id, stats, session_factory) -> None`

### Step 8 — Create `events.py`
```python
@dataclass
class ImportBatchReady:
    event_type: ClassVar[str] = "import_.ImportBatchReady"
    job_id: UUID; user_id: UUID
    rows: list[dict]  # [{date, description, amount, currency, type, category_id, source='bulk_import'}]

@dataclass
class ImportCompleted:
    event_type: ClassVar[str] = "import_.ImportCompleted"
    job_id: UUID; user_id: UUID
    imported_rows: int; skipped_rows: int; failed_rows: int
```

No event handlers — `import_` does not subscribe to any events.

### Step 9 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    event_bus.register_outbox_table("import_outbox")

def get_temporal_workflows() -> list:
    from elixir.domains.import_.workflows.import_processing import ImportProcessingWorkflow
    return [ImportProcessingWorkflow]

def get_temporal_activities(categorization_service, storage_client, session_factory) -> list:
    from elixir.domains.import_.workflows.activities import ImportActivities
    a = ImportActivities(categorization_service=categorization_service, storage_client=storage_client, session_factory=session_factory)
    return [a.detect_columns, a.parse_rows, a.apply_rules, a.store_errors, a.publish_batch_ready, a.publish_completed]
```

### Step 10 — Register router in `runtime/app.py`
Include the `import_` router under prefix `/import`.

## Verification Checklist
- [ ] Upload a CSV → job created → SSE stream returns auto-detected column mapping
- [ ] `POST /import/{job_id}/confirm-mapping` sends Temporal signal and workflow resumes
- [ ] Rows with unparseable dates/amounts are recorded in `import_row_errors`, not silently skipped
- [ ] Duplicate rows (fingerprint match) are counted in `skipped_rows`, not `failed_rows`
- [ ] `ImportBatchReady` and `ImportCompleted` are written to outbox atomically
- [ ] Deleting a completed import does NOT delete the transactions that were created
- [ ] `source_type='splitwise_csv'` uses a dedicated parser (not generic column mapping)
- [ ] Ruff + mypy pass with no errors
