# Business Intent: import_

## Why This Domain Exists

Many users come to Elixir with years of financial data already in a spreadsheet — an expense tracker they've been maintaining manually, a Splitwise export, or a CSV from another app. The statements domain handles structured bank PDFs and CSVs with a known format; it can't handle a generic spreadsheet with arbitrary column names. The import domain fills this gap: it accepts any tabular file, figures out the column layout with the user's help, and converts it into transactions in bulk.

---

## What It Provides

- **Generic CSV and XLSX import** — accepts any spreadsheet with transaction-like columns, regardless of column names or layout.
- **Auto column detection** — on upload, the system inspects the file headers and makes its best guess at which column is the date, which is the description, which is the amount. The user confirms or corrects this mapping before processing begins.
- **Durable mapping confirmation** — the user can upload a file, see the proposed column mapping, close the browser, and return later to confirm it. The workflow waits.
- **Bulk categorisation** — all rows are run through the user's categorisation rules in one pass. Rows that don't match any rule are imported as "Others" and can be re-categorised later.
- **Duplicate prevention** — rows that match transactions already in the system (same description, date, and amount) are silently skipped and counted, so re-importing the same file is safe.
- **Format-specific parsers** — Splitwise CSV exports, which have a different structure from a generic bank CSV, are handled by a dedicated parser without requiring the user to map columns manually.

---

## How a User Interacts With It

| Action | What the user does | What happens |
|---|---|---|
| Upload file | Selects a CSV or XLSX and uploads it | File is stored; header detection runs; proposed column mapping is shown to user |
| Review column mapping | Sees "Date → Column A, Description → Column B, Amount → Column C" | Confirms if correct or corrects the mapping |
| Confirm mapping | Taps "Start import" | Workflow resumes; all rows are parsed and categorised |
| View results | Import completes | Notification: "{n} transactions imported. {m} duplicates skipped" |
| Handle uncategorised rows | Views imported transactions | Rows with no matching rule appear as "Others" category and can be edited |
| Re-import same file | Uploads the same file again | Duplicate rows are skipped; only new rows are imported |

---

## User Stories

- As a user, I want to import three years of expense data from my existing spreadsheet so I have a complete financial history in Elixir.
- As a user, I want to import my Splitwise export so I can see shared expenses alongside my personal ones.
- As a user, I want the system to guess the column layout so I don't have to specify each mapping from scratch.
- As a user, I want to correct the column mapping before data is processed so I don't end up with garbage data.
- As a user, I want re-importing the same file to be safe so I don't accidentally create duplicates.
- As a user, I want to see exactly how many rows were imported and how many were skipped so I know my history is complete.

---

## What It Does Not Do

- Does not use AI for row-by-row classification. Import uses categorisation rules only, in bulk. Rows that don't match a rule are imported as "Others".
- Does not handle PDF statements. That is the `statements` domain's job.
- Does not handle bank-specific CSV formats with known structure. Bank CSVs that match a known statement format should go through the `statements` domain instead, where AI classification is available row by row.
- The import batch is all-or-nothing. If the workflow fails at any point after column mapping, zero transactions are created — there is no partial commit. The user re-uploads the same file, and duplicate rows are automatically skipped. This is stronger than 'no partial continuation': a failure leaves the ledger completely unchanged.
- Does not split amounts or detect self-transfers during import. Transfer detection happens post-import as a scan in the `transactions` domain.

---

## Key Constraint

Import is bulk and rules-only. The experience trades classification quality (no AI, everything ambiguous lands in "Others") for speed (thousands of rows processed in one pass without waiting for user confirmation on each). The user cleans up uncategorised rows afterwards via the regular transaction editing UI.
