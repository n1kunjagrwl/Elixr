# Slice: Delete Import Batch (Known Limitation)

## User Goal
Undo or reverse a completed bulk import — for example, if the wrong file was uploaded, the column mapping was accepted incorrectly, or the user wants to re-import a corrected version.

## Trigger
User notices incorrect transactions from a past import and wants to remove or undo the entire batch.

## Preconditions
- User is authenticated.
- An `import_jobs` row with `status = 'completed'` exists for this user.
- The import has already been processed: `ImportBatchReady` was consumed by the `transactions` domain and transactions were created; `ImportCompleted` was published.

---

## Current State: No Bulk Delete Feature

There is currently **no bulk-delete-import-batch feature** in Elixir. A completed import cannot be reversed or rolled back as a batch operation. This is a known limitation.

The reasons are architectural: once `ImportBatchReady` is consumed by the `transactions` domain, individual `transactions` and `transaction_items` rows are created with `source = 'bulk_import'`. These rows are owned by the `transactions` domain and have been independently processed by downstream handlers (`earnings`, `budgets`, `investments`). Rolling them back as a group would require coordinated multi-domain state reversal, which is not currently implemented.

---

## What the User Can Do Today

### Step 1: Identify Affected Transactions
**User action**: Navigates to the transaction list and filters by `source = bulk_import` and the approximate date range of the import.
**System response**: The transaction list shows all transactions created from bulk imports. The user identifies which transactions originated from the problematic import file. Because `import_jobs.id` is not stored on individual `transactions` rows, there is no single query to retrieve "all transactions from job X" — the user relies on date and source filtering plus recognising the descriptions.

### Step 2: Edit or Delete Transactions Individually
**User action**: For each incorrect transaction, either:
- **Edits it** via the transaction edit UI (slice 16) to correct the category, amount, notes, or type.
- **Deletes it** individually (if a transaction delete feature is available in the current build).

**System response**: Each edit publishes `TransactionUpdated`, which triggers retroactive budget correction via the `budgets` domain handler. Each deletion (if implemented) would need to reverse any `budget_progress` increments.

### Step 3: Re-import Corrected File
**User action**: After removing or correcting the incorrect transactions, uploads the corrected CSV via the Import screen (slice 13).
**System response**: The import workflow runs. Rows whose fingerprints match already-existing transactions are skipped (counted in `import_jobs.skipped_rows`). Only genuinely new rows are created. The user does not need to worry about creating duplicates of the transactions they kept.

---

## What a Future Delete-Batch Feature Would Need to Handle

A proper bulk-delete-import-batch feature does not exist today. If it were built, it would need to:

1. **Identify all transactions from the batch**: The `transactions` table would need an `import_job_id` column (currently absent) to allow batch-scoped queries. Without this, the association between an import job and its created transactions is lost once the event is consumed.

2. **Publish `TransactionUpdated` events for each deleted transaction**: The `budgets` domain handler for `TransactionUpdated` decrements `budget_progress.current_spend` using `old_items`. For a batch delete, this would need to be replicated for every transaction in the batch — effectively emitting a "zero new items" `TransactionUpdated` for each row to reverse budget spend.

3. **Handle earnings linkage**: Any `earnings` rows with `transaction_id` pointing to a deleted transaction would be orphaned. The feature would need to either delete the linked earnings record or set `transaction_id = NULL` (converting it to a manual earning) and notify the user to re-classify.

4. **Handle fingerprint release**: Deleted transaction fingerprints would be freed, allowing the same rows to be re-imported. The feature must decide whether to free or hold fingerprints on deletion.

5. **Handle SIP links**: If any deleted transaction had a `peer_settlements.linked_transaction_id` or an investment SIP link, those references would need to be cleared.

6. **Audit trail**: A bulk delete affecting dozens or hundreds of rows is a high-impact operation. A record of the deleted import job and the count of reversed transactions should be preserved.

## Domains Involved
- **import_**: Owns `import_jobs` and `import_column_mappings`; the import job record cannot be deleted (status is informational only).
- **transactions**: Owns the created transactions; individual edits are the current correction mechanism.
- **budgets**: Must be corrected when transactions are individually edited, via `TransactionUpdated` event processing.

## Edge Cases & Failures
- **Import created transactions that are now linked to peer settlements**: If the user manually linked an imported transaction to a `peer_settlements` row after the import, deleting that transaction would break the settlement link. In the current model (individual edit/delete path), the user must clear the settlement link before deleting the transaction.
- **Re-uploading the same file after partial correction**: If the user edited (but did not delete) some incorrect transactions, re-uploading the original file will skip those rows via fingerprint deduplication — no duplicates are created. The user must delete the transaction rows to allow re-import.
- **Import job is in status `failed` or `processing`**: This slice covers only `status = 'completed'` imports. A failed import created no transactions — there is nothing to undo. A still-processing import should be handled via the Temporal workflow cancellation path (not documented in this slice).

## Success Outcome
There is no automated success path for batch deletion today. The user's best available path is to identify and correct or delete affected transactions one at a time via the transaction edit UI, then re-import a corrected file if needed. A bulk-delete feature remains a future capability that would require the architectural additions described above.
