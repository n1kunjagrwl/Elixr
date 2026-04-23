# Slice: Classify Low-Confidence Statement Rows

## User Goal
Manually assign categories to transaction rows the AI could not confidently classify during statement processing.

## Trigger
During statement upload processing, the AI returns `confidence < 0.85` for one or more rows. The workflow pauses via Temporal `waitForSignal` and the frontend renders the row with `needs_classification: true`.

## Preconditions
- A `StatementProcessingWorkflow` is in progress (`extraction_jobs.status = 'awaiting_input'`).
- At least one `raw_extracted_rows` row has `classification_status = 'pending'`.

## Steps

### Step 1: Low-Confidence Row Presented
**User action**: None — the row arrives via SSE during the statement review stream.
**System response**: The row is displayed with:
- The raw description, date, and amount from the statement.
- The AI's suggested category (if confidence ≥ 0.5) shown as a pre-selected suggestion.
- The AI confidence score (or a UI indicator of low confidence).
- A category selector showing all active categories from `categories_for_user` (defaults + user's custom categories).

### Step 2: User Selects Category
**User action**: Taps the suggested category to confirm it, or picks a different category from the dropdown.
**System response**: Nothing committed yet — the selection is held in frontend state.

### Step 3: Optional — Add Item Breakdown
**User action**: Optionally expands the row to add item-level labels and amounts (e.g., for a ₹500 Swiggy order: "Butter Chicken ₹250, Naan ₹150, Delivery ₹100").
**System response**: Frontend validates that item amounts sum to the transaction total before allowing submission.

### Step 4: Submit Classification
**User action**: Taps "Confirm" on the row.
**System response**: `POST /statements/{job_id}/rows/{row_id}/classify` is called with the selected `category_id` and optional `items` array. The API looks up `extraction_jobs.temporal_workflow_id` and sends a Temporal signal to the running workflow. The workflow receives the signal, records the classification on the `raw_extracted_rows` row (`classification_status = 'user_classified'`, `final_category_id`, `final_items`), increments `extraction_jobs.classified_rows`, and continues to the next row.

### Step 5: Workflow Resumes
**User action**: None — happens automatically.
**System response**: The workflow proceeds to the next pending row. If more low-confidence rows remain, another `waitForSignal` is entered and the next row is streamed to the frontend. When all rows are classified, `ExtractionCompleted` is published.

## Domains Involved
- **statements**: Owns `raw_extracted_rows` and `extraction_jobs`; receives Temporal signals via the classify endpoint; runs `StatementProcessingWorkflow`.
- **categorization**: `suggest_category()` produced the initial low-confidence suggestion.
- **transactions**: Ultimately consumes `ExtractionCompleted` to create records.

## Edge Cases & Failures
- **User closes browser / app during classification**: The Temporal workflow holds state durably. The workflow remains in `awaiting_input` state. When the user returns (same device or different), they can navigate to the in-progress statement and resume. See slice `11-resume-abandoned-statement.md`.
- **User submits a category that doesn't match the transaction type**: E.g., assigning an income category to a debit row. The service layer validates `category.kind` matches the transaction type (debit → expense or transfer; credit → income or transfer). Mismatch returns a validation error.
- **Items don't sum to transaction amount**: Frontend blocks submission. The user must adjust item amounts before confirming.
- **User skips a row**: The row can be marked as `skipped` — it will not become a transaction. This is valid for rows the user knows are not real transactions (e.g., opening balance rows on some statement formats).

## Success Outcome
Every low-confidence row is manually classified. The workflow resumes and eventually completes with `ExtractionCompleted`, creating all transaction records.
