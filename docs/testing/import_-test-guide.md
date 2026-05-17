# import_ — E2E Test Guide

> Last generated: 2026-05-17

## Business Intent

The import_ domain lets a user bring years of existing financial history into Elixir from any CSV or XLSX spreadsheet, regardless of column layout. The user uploads the file, reviews or corrects an auto-detected column mapping, and confirms it; the system then parses all rows in bulk, deduplicates against existing transactions by fingerprint, applies categorisation rules, and creates transaction records. Re-uploading the same file is safe — duplicate rows are silently skipped and counted. Rows that match no categorisation rule are imported as "Others" for later manual review. If the workflow fails at any point after mapping confirmation, zero transactions are committed — the ledger is left completely unchanged and the user simply re-uploads the corrected file.

---

## Domain Scope

| Item | Detail |
|------|--------|
| Tables owned | `import_jobs`, `import_column_mappings`, `outbox` |
| Events published | `ImportBatchReady` (consumed by `transactions`), `ImportCompleted` (consumed by `notifications`) |
| Events consumed | None — import is triggered by HTTP file upload only |
| Temporal workflows | `ImportProcessingWorkflow` (pauses on `waitForSignal(ColumnMappingConfirmed)`) |
| Slices covered | 13, 14, 43 |

---

## Test Scenarios

---

### Scenario 1: Successful end-to-end import of a generic CSV

**Source slice**: `docs/slices/13-import-csv-bulk.md`
**Business intent**: A user uploads a generic CSV with historical transactions and, after confirming the auto-detected column mapping, all valid rows are parsed, deduplicated, categorised, and committed as transactions.
**Domains involved**: import_, categorization, transactions, notifications

#### Preconditions
- User is authenticated.
- At least one categorisation rule exists for the user (to verify rule-based categorisation fires; uncategorised rows are also acceptable).
- No transactions exist in the ledger that share fingerprints with rows in the test file.
- Test file is a valid CSV with recognisable headers (`Date`, `Description`, `Amount`) and at least 3 data rows.

#### Steps
1. `POST /import/upload` — upload the test CSV file.
2. Poll or subscribe to SSE until `import_jobs.status = 'awaiting_mapping'` is observed.
3. Read the proposed column mapping returned by the SSE stream.
4. `POST /import/{job_id}/mapping/confirm` — submit the auto-detected mapping unchanged.
5. Poll or subscribe to SSE until `import_jobs.status = 'completed'` is observed.

#### Assertions
- **DB**: `import_jobs` row exists with `status = 'completed'`, `imported_rows > 0`, `failed_rows = 0`, `completed_at IS NOT NULL`.
- **DB**: `import_column_mappings` rows exist for the job — one row per source column, each with a non-null `mapped_to` value.
- **DB**: `transactions` rows exist with `source = 'bulk_import'` and count equal to `import_jobs.imported_rows`.
- **DB**: File is deleted from storage after completion (`file_path` should no longer resolve to an existing object).
- **API response**: `GET /import/{job_id}` returns `status = 'completed'`, `imported_rows`, `skipped_rows`, `failed_rows`, `total_rows`.
- **Events**: `ImportBatchReady` outbox row was written and processed (no undelivered outbox rows for this job).
- **Events**: `ImportCompleted` outbox row was written with correct counts.
- **Side effects**: A notification banner exists for the user with title "Import finished" and body referencing the correct counts.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| All rows are duplicates (same file re-uploaded) | `imported_rows = 0`, `skipped_rows = total_rows`, `status = 'completed'` — import is still considered successful | [ ] |
| Some rows are duplicates, some are new | `imported_rows` equals only the new rows; `skipped_rows` equals duplicate count; no duplicate transactions created | [ ] |
| File has rows with no matching categorisation rule | Those rows are created as transactions with category "Others" | [ ] |
| File has a `category` column and that column is mapped | Rows with recognised category values use the mapped category; others fall back to "Others" | [ ] |
| Workflow fails mid-run (simulated Temporal failure after mapping confirmed) | `import_jobs.status = 'failed'`; zero transactions created; ledger unchanged — atomic all-or-nothing (see Known Inconsistencies §3.11) | [ ] |
| Large file (1000+ rows) | All rows processed in a single workflow execution; `total_rows` and `imported_rows` match expectations; no timeout or partial commit | [ ] |
| Mixed currencies in the file | Each row's currency is parsed or defaults to the user's primary currency; transactions created with correct currency values | [ ] |
| Splitwise CSV upload (`source_type = 'splitwise_csv'`) | Dedicated Splitwise parser handles who-paid/who-owes columns; shared expenses become debits, received splits become credits; column mapping confirmation step is skipped or pre-filled | [ ] |

---

### Scenario 2: Column mapping confirmation — auto-detection correct

**Source slice**: `docs/slices/14-confirm-column-mapping.md`
**Business intent**: The system auto-detects column roles from file headers; the user reviews the proposed mapping and confirms without changes.
**Domains involved**: import_ only

#### Preconditions
- User is authenticated.
- An `import_jobs` row with `status = 'awaiting_mapping'` exists (created by completing Scenario 1 Step 1–2).
- The file has headers that match common heuristics (`Date`, `Description`, `Amount` or equivalent).

#### Steps
1. Observe the mapping returned by SSE or `GET /import/{job_id}` after upload.
2. Verify the proposed mapping covers the required fields.
3. `POST /import/{job_id}/mapping/confirm` — submit the mapping as returned without modification.
4. Poll until `import_jobs.status` transitions from `awaiting_mapping` to `processing` then `completed`.

#### Assertions
- **DB**: `import_column_mappings` rows are inserted — one per source column; `date`, `description`, and at least one of `amount` / `debit_amount` / `credit_amount` are present.
- **DB**: `import_jobs.status` transitions through `awaiting_mapping → processing → completed` in order.
- **API response**: `POST /import/{job_id}/mapping/confirm` returns 200 and the workflow resumes (status moves to `processing` promptly).
- **Events**: `ColumnMappingConfirmed` Temporal signal is delivered and the workflow resumes.
- **Side effects**: None beyond workflow resumption.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| File has no header row | Auto-detection fails to assign meaningful names; columns are labelled A, B, C; user must map manually using column letters | [ ] |
| Required field (`date`) not present in the proposed mapping | `POST /import/{job_id}/mapping/confirm` is rejected (client-side guard prevents submission; if bypassed, API returns 422) | [ ] |
| Required field (`description`) not present in the proposed mapping | Same as above | [ ] |
| Required field (amount) not present — neither `amount` nor `debit_amount`/`credit_amount` mapped | Confirm button disabled; API returns 422 if bypassed | [ ] |

---

### Scenario 3: Column mapping confirmation — user corrects auto-detection

**Source slice**: `docs/slices/14-confirm-column-mapping.md`
**Business intent**: When auto-detection assigns the wrong role to a column (e.g., "Narration" not detected as description), the user corrects it before confirming, preventing garbage data in the ledger.
**Domains involved**: import_ only

#### Preconditions
- User is authenticated.
- An `import_jobs` row with `status = 'awaiting_mapping'` exists.
- The test file has a non-standard header (e.g., `Narration` instead of `Description`) that auto-detection may or may not recognise — use a file where at least one column is intentionally misdetected.

#### Steps
1. Observe the auto-detected mapping from SSE / `GET /import/{job_id}`.
2. Identify at least one incorrectly mapped column.
3. `POST /import/{job_id}/mapping/confirm` — submit a corrected mapping (override the misdetected column to its correct role).
4. Poll until `import_jobs.status = 'completed'`.

#### Assertions
- **DB**: `import_column_mappings` rows reflect the user-corrected mapping, not the original auto-detected one.
- **DB**: Transactions created use the corrected column layout (e.g., dates come from the correct column, descriptions are readable text not raw amounts).
- **API response**: Confirm endpoint returns 200.
- **Events**: Workflow resumes using the corrected mapping payload carried in the `ColumnMappingConfirmed` signal.
- **Side effects**: None.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Two source columns both mapped to `description` | Parser concatenates both values for that row's description field (e.g., "NEFT - Reference 123456") | [ ] |
| Single signed `amount` column mapped as `amount` | Positive rows become `type = 'credit'`; negative rows become `type = 'debit'` | [ ] |
| Separate `Debit` and `Credit` columns each mapped correctly | Rows with a value in the debit column get `type = 'debit'`; credit column rows get `type = 'credit'`; rows with both populated — TODO: document parser behaviour | [ ] |
| User confirms an incorrect mapping (e.g., date and amount swapped) and import completes | Transactions are created with malformed data; user must manually edit or delete them individually (batch rollback is not available — see Scenario 4) | [ ] |
| Sample preview shown before confirmation reflects actual parsed output for first 5 rows | Preview rows match the final imported transaction data for those rows | [ ] |

---

### Scenario 4: Delete / rollback import batch — current limitation

**Source slice**: `docs/slices/43-delete-import-batch.md`
**Business intent**: A user who imported the wrong file or confirmed an incorrect mapping wants to undo the entire batch; this feature does not currently exist and the user must correct transactions individually.
**Domains involved**: import_, transactions, budgets

#### Preconditions
- User is authenticated.
- An `import_jobs` row with `status = 'completed'` exists.
- Transactions with `source = 'bulk_import'` exist from that job.

#### Steps
1. Attempt to find a bulk-delete or rollback endpoint for the import job (e.g., `DELETE /import/{job_id}`).
2. If no such endpoint exists, verify the workaround path: filter the transaction list by `source = bulk_import` and the approximate date range, then delete or edit transactions individually.
3. After individual corrections, re-upload the corrected CSV via the normal import flow (Scenario 1).

#### Assertions
- **API response**: No bulk-delete endpoint currently exists. Any attempt to call `DELETE /import/{job_id}` should return 404 or 405. (TODO: confirm exact error code once API surface is finalised.)
- **DB**: `import_jobs` row and `import_column_mappings` rows are NOT deleted even after individual transactions are removed — the job record is informational and immutable.
- **DB**: Individual transaction edits publish `TransactionUpdated`; `budget_progress.current_spend` is decremented correctly by the budgets domain handler.
- **DB**: After deleting individual transactions, re-uploading the same file creates only the rows whose fingerprints were freed by deletion; rows that were kept (only edited, not deleted) are skipped as duplicates.
- **Events**: Each individual transaction deletion or edit emits `TransactionUpdated`; no batch-level event exists.
- **Side effects**: If any imported transaction was manually linked to a `peer_settlements` row after import, that settlement link must be cleared by the user before the transaction can be deleted.

#### Edge Cases

| Condition | Expected outcome | Verified? |
|-----------|-----------------|-----------|
| Import job `status = 'failed'` — no transactions were created | Nothing to undo; the failed job record remains; user simply re-uploads | [ ] |
| Import job `status = 'processing'` — workflow still running | Cancellation path not covered in this slice; TODO: document Temporal workflow cancellation path | [ ] |
| Imported transaction linked to a peer settlement | Transaction cannot be deleted until the settlement link is cleared manually | [ ] |
| Re-uploading the original file after partial correction (some rows edited but not deleted) | Edited rows are still present with matching fingerprints and are skipped; only genuinely deleted rows can be re-imported | [ ] |
| Future bulk-delete feature | Would require `transactions.import_job_id` column (currently absent), multi-domain coordination (budgets, earnings, investments, peers), fingerprint release decision, and audit trail — not implemented | [ ] |

---

## Known Inconsistencies

- **[3.11]** Bulk import is all-or-nothing (atomic): `docs/business-intent/import_.md` describes this as "no partial import continuation", which implies the user loses partial progress. The actual behaviour, documented in `docs/slices/13-import-csv-bulk.md`, is stronger: a mid-run workflow failure means zero rows are committed. The ledger is left completely unchanged. The word "atomic" is absent from the business intent but is the correct characterisation. Tests must assert that a simulated failure after mapping confirmation leaves zero transactions created, not a partial set.

---

## Coverage Gaps

| Gap | Source | TODO |
|-----|--------|------|
| No bulk-delete-import-batch endpoint exists | `docs/slices/43-delete-import-batch.md` | Scenario 4 is currently a workaround path only. If a bulk-delete feature is built, add a new scenario covering the full deletion flow and multi-domain coordination. |
| `transactions.import_job_id` column is absent | `docs/slices/43-delete-import-batch.md` | There is no reliable way to query "all transactions from import job X". Tests for Scenario 4 must rely on `source = 'bulk_import'` + date-range filtering, which is approximate. |
| Splitwise CSV parser behaviour is not fully specified | `docs/slices/13-import-csv-bulk.md` | Edge case: does the Splitwise parser skip the column-mapping confirmation step entirely (layout is known), or does it pre-fill the mapping and allow user review? Clarify before writing tests for the Splitwise path. |
| Two-column debit/credit layout — row has values in both columns | `docs/slices/14-confirm-column-mapping.md` | Parser behaviour for a row where both debit_amount and credit_amount are non-zero is unspecified. Verify with domain owner before asserting expected outcome. |
| `ImportCompleted` count discrepancy | `docs/domains/import_.md` (count discrepancy note) | `imported_rows` in `ImportCompleted` reflects rows submitted by the import domain, not transactions actually created (the `transactions` domain may skip additional duplicates). Tests that assert notification body counts must use the import domain's count, not the transactions table count. Document the delta expectation explicitly. |
| Temporal workflow cancellation for in-progress imports | `docs/slices/43-delete-import-batch.md` | No slice covers cancelling a running `ImportProcessingWorkflow`. Test behaviour for `status = 'processing'` imports is undefined. |
| `GET /import/{job_id}` response schema | Not documented in the files reviewed | Confirm the exact response shape (field names, status enum values) against the API implementation before asserting API response shape in tests. |

---

## TODO

- [ ] Confirm whether the Splitwise CSV path bypasses or pre-fills the column mapping step — adjust Scenario 1 Splitwise edge case accordingly.
- [ ] Determine the exact HTTP status code returned when attempting to call a non-existent bulk-delete endpoint (`DELETE /import/{job_id}`) — update Scenario 4 assertion.
- [ ] Clarify parser behaviour when both `debit_amount` and `credit_amount` are non-zero in the same row — add as an edge case in Scenario 3.
- [ ] Write a dedicated test for the `ImportCompleted` count discrepancy: import a file where some rows are also present in a prior statement upload; assert `import_jobs.imported_rows` differs from `SELECT COUNT(*) FROM transactions WHERE source = 'bulk_import'` and that the notification uses the import domain's count.
- [ ] Once (or if) a bulk-delete-import-batch feature is built, replace Scenario 4's workaround steps with the real feature flow and add assertions for: `TransactionUpdated` events per deleted row, `budget_progress.current_spend` decrements, earnings orphan handling, fingerprint release, and audit trail creation.
- [ ] Add a test for the SSE stream: verify `status` transitions (`uploaded → awaiting_mapping → processing → completed`) are streamed in order and carry correct `total_rows` and progress fields.
- [ ] Verify that `import_jobs.file_path` is deleted from storage on completion and also on failure (no orphaned files).
