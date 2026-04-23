# Slice: View Portfolio Historical Value Chart

## User Goal
See how the total portfolio value has changed over time — weekly, monthly, or since inception.

## Trigger
User taps "View history" or the portfolio chart on the Investments screen.

## Preconditions
- At least one `valuation_snapshots` row exists for the user's holdings.

## Steps

### Step 1: Open Portfolio History
**User action**: Taps the portfolio value chart or "View history" button.
**System response**: The API queries `valuation_snapshots` for all holdings belonging to this user, grouped by `snapshot_date`. For each date, the total portfolio value is `SUM(snapshot.value)` after converting each holding's snapshot value to INR using the FX rate closest to that date.

### Step 2: Select Time Range
**User action**: Selects a time range: 1 week | 1 month | 3 months | 6 months | 1 year | all time.
**System response**: The query filters `snapshot_date` to the selected range. The chart renders a line graph with portfolio value on the Y-axis and date on the X-axis.

### Step 3: View Individual Holding History
**User action**: Taps a specific holding on the portfolio screen → "View chart".
**System response**: Queries `valuation_snapshots WHERE holding_id = :id` filtered by the same date range. Shows the holding's value trajectory in its native currency.

### Step 4: Identify Value Milestones
**User action**: Taps on a data point on the chart.
**System response**: Shows the portfolio value and composition on that specific date — which holdings were held and their values. (This requires joining `valuation_snapshots` for the selected date across all holdings.)

## Domains Involved
- **investments**: Owns `valuation_snapshots`; provides historical data.
- **fx**: Historical FX rates used for cross-currency aggregation (`as_of_date` parameter in `fx.convert()`).

## Edge Cases & Failures
- **Gaps in snapshot history** (e.g., the valuation workflow didn't run on a particular day): The chart interpolates or shows the last known value for that day. The workflow upserts by `(holding_id, snapshot_date)` — if a day is missed, no snapshot exists and the gap is visible.
- **Holding added recently**: History only exists from the holding's creation date. The chart shows a flat line (or no data) for dates before the holding was added.
- **FX rate not available for a historical date**: `fx.convert()` with `as_of_date` falls back to the closest available rate. The rate used is shown as a footnote ("Exchange rate as of {date}").

## Success Outcome
User sees a clear chart of portfolio value over the selected time range, helping them understand growth trends and the impact of market movements.
