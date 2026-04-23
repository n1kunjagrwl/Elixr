# Slice: Add Investment Holding

## User Goal
Log a new investment position (stock, mutual fund, ETF, PPF, gold, crypto, NPS, SGB, US stock, RD, bond, or other) so it appears in the portfolio with a current valuation.

## Trigger
User taps "Add Investment" on the Portfolio screen or the Investments tab.

## Preconditions
- User is authenticated.
- For instrument types that require live pricing (stock, etf, mf, crypto, gold, us_stock, sgb), the instrument must either already exist in the `instruments` master table or the user provides enough detail to create it.

## Steps

### Step 1: Select Instrument Type
**User action**: User taps "Add Investment" and is shown a type picker: Stock, Mutual Fund, ETF, Fixed Deposit, PPF, Bond, NPS, SGB, Crypto, Gold, US Stock, RD, Other.

**System response**: UI renders the appropriate input form based on the selected type. FD type routes to the dedicated FD slice (28). All other types continue in this slice.

### Step 2: Search or Identify the Instrument
**User action**: For market-traded types (stock, mf, etf, crypto, gold, us_stock, sgb), the user types a name or ticker into a search field. For non-traded types (ppf, bond, nps, rd, other), the user enters a free-text name.

**System response**:
- Backend queries the `instruments` table by `ticker` or `name` (case-insensitive partial match) filtered by `type`.
- Matching instruments are returned as suggestions. If an exact match exists, it is pre-selected.
- If no match is found and the type supports auto-creation (e.g. crypto symbol), a "Create new instrument" option is shown with the entered text pre-filled as `name` and `ticker`.

### Step 3: Confirm Instrument Details
**User action**: User selects an instrument from suggestions or confirms the new-instrument form. For a new instrument the user may fill in `isin` (optional), `exchange` (optional), `currency` (default INR).

**System response**: If the instrument does not yet exist in `instruments`, the backend inserts a new row. The `data_source` field is set based on type (e.g. NSE feed for stocks, AMFI for MF). The `govt_rate_percent` field is populated for PPF/NPS types from a system config default (currently 7.1% for PPF). The new instrument `id` is returned.

### Step 4: Enter Holding Details
**User action**: User fills in:
- **Units** — number of units / shares / grams held (numeric, up to 6 decimal places).
- **Average cost per unit** — the blended purchase price per unit.
- **Total invested** — optionally overridden; otherwise auto-computed as `units × avg_cost_per_unit` and shown as a hint.
- **As of date** — defaults to today; user may backdate.

**System response**: UI shows a live preview of total invested. If `total_invested` is manually entered and differs from `units × avg_cost_per_unit` by more than 0.5%, the UI shows a reconciliation warning but does not block submission.

### Step 5: Submit
**User action**: User taps "Save Holding".

**System response**:
1. Backend inserts a row into `holdings`:
   - `user_id`, `instrument_id`, `units`, `avg_cost_per_unit`, `total_invested` stored as provided.
   - `current_price` and `current_value` set to `null` initially; `last_valued_at` set to `null`.
2. For market-traded types, the next run of **MarketPriceFetchWorkflow** (within 15 minutes during market hours, or at next open) fetches the live price and updates `current_price`, `current_value`, `last_valued_at`.
3. For calculated types (ppf, bond, nps, rd), the next run of **CalculatedValuationWorkflow** (daily 00:30 IST) computes the current value and updates the holding.
4. A `valuation_snapshots` row is upserted for today once a price is available.
5. The portfolio screen shows the new holding immediately with "Valuation pending" if no price is available yet.

## Domains Involved
- **Investments**: Core domain. Creates `instruments` row if needed, creates `holdings` row, triggers valuation via background workflows.
- **Transactions** (indirect): If the user later links this holding to a transaction, that linkage is handled separately.

## Edge Cases & Failures
- **Duplicate holding**: If a `holdings` row already exists for the same `user_id` + `instrument_id`, the backend returns a 409 Conflict with a message "You already hold this instrument. Edit the existing holding instead."
- **Instrument creation fails (duplicate ticker)**: If two users try to create the same instrument simultaneously, the second insert hits a unique constraint on `ticker` + `type`; the backend retries with a SELECT to return the existing instrument id.
- **Invalid units or cost**: Non-positive values are rejected with a 422 validation error and a field-level message.
- **Unsupported currency**: Only currencies listed in the system config are accepted; others return a 422.
- **Market closed / price unavailable**: Holding is saved with null valuation; a "Valuation pending" badge is shown until MarketPriceFetchWorkflow or CalculatedValuationWorkflow fills it in.
- **Network error during submit**: The frontend retries with idempotency key; duplicate inserts are prevented by the unique constraint.

## Success Outcome
A new holding row exists in the database linked to the correct instrument. The portfolio screen displays the holding with total invested amount immediately, and current market value populates within 15 minutes (market-traded) or by next morning (calculated types).
