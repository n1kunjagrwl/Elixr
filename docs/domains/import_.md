# Domain: import_

## Responsibility

Handles bulk import of historical transaction data from CSV files or spreadsheets (Excel/XLSX). This is distinct from the `statements` domain, which processes bank-formatted statements (PDF or structured CSV). The import domain handles generic tabular data — a user's existing expense spreadsheet, a Splitwise export, or a custom CSV they've been maintaining. Column layouts are not known in advance; the user maps them interactively.

Like statement processing, import is a Temporal workflow with a human-in-the-loop step (column mapping confirmation). Unlike statement processing, import applies categorisation rules in bulk rather than row-by-row AI classification.

---

## Tables Owned

### `import_jobs`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `file_path` | `text` NOT NULL | User-scoped storage path |
| `original_filename` | `text` | For display |
| `source_type` | `text` NOT NULL | `csv_generic` \| `xlsx_generic` \| `splitwise_csv` (more added as needed) |
| `temporal_workflow_id` | `text` | For sending ColumnMappingConfirmed signal |
| `status` | `text` NOT NULL DEFAULT `'uploaded'` | `uploaded` \| `awaiting_mapping` \| `processing` \| `completed` \| `failed` |
| `total_rows` | `int` NULLABLE | Set after file is parsed |
| `imported_rows` | `int` DEFAULT 0 | Rows successfully created as transactions |
| `skipped_rows` | `int` DEFAULT 0 | Duplicate fingerprints (already exist) |
| `failed_rows` | `int` DEFAULT 0 | Rows that could not be parsed |
| `error_log` | `jsonb` NULLABLE | `[{row_index, reason}]` for failed rows |
| `created_at` | `timestamptz` | — |
| `completed_at` | `timestamptz` NULLABLE | — |

### `import_column_mappings`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `job_id` | `uuid` FK → `import_jobs.id` | — |
| `source_column` | `text` NOT NULL | Column name as it appears in the uploaded file |
| `mapped_to` | `text` NOT NULL | `date` \| `description` \| `debit_amount` \| `credit_amount` \| `amount` \| `balance` \| `category` \| `ignore` |

`amount` is used when the file has a single signed amount column (positive = credit, negative = debit). `debit_amount` and `credit_amount` handle two-column layouts.

### `outbox`
Standard outbox table.

---

## SQL Views Exposed

None.

---

## Events Published

### `ImportBatchReady`
```python
@dataclass
class ImportBatchReady:
    event_type = "import_.ImportBatchReady"
    job_id: UUID
    user_id: UUID
    rows: list[dict]  # [{date, description, amount, currency, type, category_id, source='bulk_import'}]
```
Published after all rows are parsed and categorised. Consumed by: `transactions` (creates transaction and transaction_items records from `rows`)

### `ImportCompleted`
```python
@dataclass
class ImportCompleted:
    event_type = "import_.ImportCompleted"
    job_id: UUID
    user_id: UUID
    imported_rows: int
    skipped_rows: int
    failed_rows: int
```
Published after the `transactions` domain has processed the batch. Consumed by: `notifications` (creates an "Import finished" banner)

---

## Events Subscribed

None. Import is triggered by an HTTP file upload.

---

## Temporal Workflow

### `ImportProcessingWorkflow`

See [workflows/import-processing.md](../workflows/import-processing.md).

Summary:
1. Read file → detect source_type → auto-detect columns using header heuristics
2. Present detected column mapping to user (SSE stream, same as statement processing)
3. Pause on `waitForSignal(ColumnMappingConfirmed)` — user confirms or corrects mapping
4. Parse all rows using confirmed mapping
5. For each row: compute fingerprint, check for duplicates, apply categorisation rules
6. Publish `ImportBatchReady` (via outbox) — `transactions` domain subscribes and creates records
7. Publish `ImportCompleted`

---

## Key Design Decisions

**`import_` domain is separate from `statements`.** Statement processing expects a structured financial document from a known source (a bank or card). Import handles arbitrary user-maintained data. The two flows have different column-mapping requirements, different AI usage (statement uses ADK; import uses rules-only), and different user experiences. Keeping them separate makes each simpler.

**Column mapping as a Temporal signal.** Like statement processing, the workflow pauses after auto-detecting columns and waits for the user to confirm. This means a user can upload a large file, see the proposed mapping, correct it, and the workflow resumes — even if they close the browser and come back later. Temporal holds the state durably.

**Fingerprint deduplication prevents re-importing.** SHA-256 of `lower(trim(description)) + date.isoformat() + str(abs(amount))`. If the user uploads the same CSV twice, or uploads a file that overlaps with a previously uploaded bank statement, duplicate rows are skipped and counted in `skipped_rows`. The user sees exactly how many were skipped.

**Rules-only categorisation, no AI.** Import processes potentially thousands of historical rows. Using the ADK agent row-by-row would be slow and expensive. Categorisation rules are applied in bulk; uncategorised rows are imported as `Others` and the user can re-categorise them later via the transaction edit UI. This trades categorisation quality for speed.

**`source_type` allows format-specific parsers.** A Splitwise CSV export has a known structure (different columns, split amounts). Registering `splitwise_csv` as a named source type allows a dedicated parser that handles Splitwise-specific logic (who paid, who owes) without generic column mapping. Additional source types can be added without changing the workflow.
