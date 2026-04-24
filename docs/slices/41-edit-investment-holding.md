# Slice: Edit Investment Holding

## User Goal
Correct or update a holding's units, average cost, total invested amount, or the as-of date after it was initially created — for example to reflect additional purchases, a unit correction, or updated cost basis.

## Trigger
User navigates to a holding in the Portfolio screen and selects "Edit holding".

## Preconditions
- User is authenticated.
- The `holdings` row exists and belongs to this user.

## Steps

### Step 1: Open Holding Edit Form
**User action**: Taps a holding → taps "Edit holding".
**System response**: The edit form is pre-filled with the current values from the `holdings` row:
- `units` — number of units/shares/grams currently held
- `avg_cost_per_unit` — weighted average purchase price per unit
- `total_invested` — cumulative cash invested
- `as_of_date` — the date these figures are accurate as of (stored in `holdings.created_at` or tracked separately as metadata; the user enters this when editing to indicate the effective date of the correction)

The following fields are shown read-only and cannot be changed after initial creation:
- **Instrument** (`instrument_id` and `instruments.name`) — the security, fund, or asset this holding tracks
- **Type** (`instruments.type`) — e.g., `stock`, `mf`, `fd`, `crypto`

A note is shown: "To change the instrument, delete this holding and create a new one."

For `fd` type holdings, an additional "Edit FD details" section is shown (see Step 3).

### Step 2: Edit Holding Fields
**User action**: Updates one or more of the editable fields:
- **units**: Corrected unit count. For mutual funds, up to 6 decimal places are accepted. For whole-unit instruments (stocks, crypto), decimal input is allowed but the user is warned if a non-integer value is entered for a stock.
- **avg_cost_per_unit**: Corrected weighted average cost. Should reflect all purchases to date.
- **total_invested**: Corrected total cash outlay. The system does not enforce that `total_invested == units × avg_cost_per_unit` — both values are user-provided and stored independently to accommodate rounding differences across multiple purchases.
- **as_of_date**: The effective date of this correction. Stored to give context when reviewing the holding later.

### Step 3: Edit FD Details (FD holdings only)
**User action**: (For `fd` type only) — Updates FD-specific fields in the "Edit FD details" section:
- `principal` — the deposited amount
- `rate_percent` — annual interest rate
- `tenure_days` — total FD tenure
- `start_date` — FD opening date
- `compounding` — monthly / quarterly / annually / simple

**System response**: The `fd_details` row is updated alongside the `holdings` row in the same service call. `maturity_date` is recomputed as `start_date + tenure_days` and `maturity_amount` is recomputed using the compound interest formula: `P × (1 + r/n)^(n×t)`. Both are stored on the `fd_details` row.

### Step 4: Save Changes
**User action**: Taps "Save".
**System response**: The `holdings` row is updated in place (`updated_at` refreshed). For FD holdings, the `fd_details` row is updated in the same transaction.

`current_value` and `current_price` on the `holdings` row are **not** recalculated at save time. The edited `units` and cost figures are stored immediately, but the next valuation workflow run will compute a fresh `current_value` based on the updated `units` and the latest market price (or recalculated FD formula). Until the next workflow run, `last_valued_at` may be stale relative to the edited `units`.

No events are published by the edit. The `ValuationUpdated` event is published by the valuation workflow on its next scheduled run — not by this user-initiated edit.

### Step 5: Holding Reflects Edited Values
**User action**: Returns to the Portfolio screen.
**System response**: The holding card shows the updated `units`, `avg_cost_per_unit`, and `total_invested`. The `current_value` shown is the last computed value (from the previous valuation run) — a staleness note ("Value as of {last_valued_at}") is displayed until the next workflow run refreshes it.

## Domains Involved
- **investments**: Owns `holdings` and `fd_details`; performs the update; no events published at edit time.

## Edge Cases & Failures
- **Editing units to zero**: The holding row is not deleted — a zero-unit holding is stored in history. The Portfolio screen may filter out zero-unit holdings from the active view, but the row remains for historical reference. To fully remove a holding, the user must delete it explicitly (a separate "Delete holding" action not covered by this slice).
- **`current_value` appears inconsistent after edit**: Expected. For example, if the user increases `units` from 10 to 15, the portfolio screen will show the old `current_value` (based on 10 units) until the next `MarketPriceFetchWorkflow` or `CalculatedValuationWorkflow` run. The "Value as of" timestamp makes this staleness visible.
- **Editing an FD's start_date such that maturity_date is in the past**: Allowed. The `CalculatedValuationWorkflow` will compute the final maturity amount as the holding's value, since the FD has matured.
- **Editing avg_cost_per_unit but not total_invested**: Both fields are stored independently. The user is not required to keep them mathematically consistent. If inconsistency would cause confusion (e.g., `avg_cost_per_unit × units` does not match `total_invested`), the UI may show both values and a note that they were entered separately — but no validation error is raised.
- **Concurrent valuation workflow run during edit**: The workflow reads `holdings` rows at the start of each run. If the user saves an edit while the workflow is mid-run, the edit may or may not be picked up in that run. The next scheduled run will always use the latest values. No data corruption occurs — the workflow only writes to `current_value`, `current_price`, `last_valued_at`, and `valuation_snapshots`; it does not overwrite `units`, `avg_cost_per_unit`, or `total_invested`.

## Success Outcome
The holding reflects the corrected units, cost basis, and (for FDs) updated terms. The portfolio summary will show an updated `current_value` after the next valuation workflow run.
