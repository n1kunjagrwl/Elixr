# Business Intent: statements

## Why This Domain Exists

The fastest way for a user to populate Elixir with real data is to upload a PDF or CSV bank statement — a single file that contains months of transactions. Without this domain, the only option would be to enter every transaction by hand. The statements domain handles the entire journey from uploaded file to a reviewed, categorised set of transactions: it extracts rows from the file, runs them through AI classification, and streams results to the user in real time. It also ensures the process is resumable — if the user closes the app mid-review, their progress is not lost.

---

## What It Provides

- A way to **upload a bank or credit card statement** (PDF or CSV) and have it processed automatically.
- **Row-by-row AI classification** — each extracted transaction is sent to the AI agent for a category suggestion. High-confidence results are auto-applied, but remain editable by the user before final commit.
- **Real-time streaming** of classified rows so the user sees results appear progressively rather than waiting for a batch to finish.
- **Human-in-the-loop classification** — for low-confidence rows, the workflow pauses and asks the user to confirm or correct the category before moving on.
- **Durable progress** — the user can close the browser mid-classification and resume exactly where they left off.
- **Overlap detection** — if the uploaded statement covers dates already imported, the user is warned before any duplicates are created.
- **Partial completion handling** — if a statement times out before all rows are classified, the classified rows are saved and the user is told which date range needs to be re-uploaded.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Upload statement | Selects account and uploads PDF or CSV | File is stored; extraction workflow starts |
| Watch progress | Stays on the review screen | Classified rows appear one by one as the AI processes them |
| Confirm a row | AI suggests "Food & Dining" for a Swiggy transaction | User taps confirm; workflow moves to the next row |
| Correct a row | AI suggests "Shopping" for a Swiggy transaction | User changes to "Food & Dining" and submits |
| Add item breakdown | User wants to split a ₹500 Swiggy bill by dish | User enters item labels and amounts |
| Abandon and resume | User closes the app mid-review | Workflow pauses; user can return later and continue from the same row |
| Re-upload partial statement | Some rows were discarded due to timeout | User uploads the same file; already-classified rows are skipped automatically |
| Skip a row | Marks a row as not a real transaction (e.g. an opening balance line on some statement formats) | The row is marked `skipped` and will never become a transaction. It is excluded from the final commit. |
| Override an auto-classified row | Taps an auto-classified row and changes its category | The category is overridden with the user's choice; `classification_status` becomes `user_classified`. The workflow continues. |

---

## User Stories

- As a user, I want to upload my bank statement so I don't have to enter every transaction manually.
- As a user, I want to see transactions classified automatically so the common cases require no effort from me.
- As a user, I want to be asked when the AI is unsure so I remain in control of how my money is categorised.
- As a user, I want to be able to close the app and come back to finish classifying a statement later.
- As a user, I want to know if I've already imported a statement for a given date range so I don't accidentally create duplicates.
- As a user, I want to see how many rows were processed and if any were skipped, so I know my data is complete.

---

## What It Does Not Do

- Does not store the original statement file after processing. The file is deleted once rows are extracted; only the extracted data is kept.
- Does not create transactions directly. Transactions are only created by the `transactions` domain after the user confirms classification results.
- Does not perform deduplication itself. Fingerprint-based deduplication happens in the `transactions` domain when rows are committed.
- Does not support all statement formats from all banks. Parsing quality depends on the structure of the PDF or CSV.

---

## Key Constraint

A statement row does not become a transaction until the user confirms its classification. This staging separation means the user can review, correct, and abandon without affecting the transaction ledger. A transaction is created only as a result of a confirmed extraction.
