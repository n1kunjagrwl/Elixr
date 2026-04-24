# Implementation Plan: investments

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/investments.md`](../domains/investments.md)
- Data model: [`docs/data-model.md`](../data-model.md#investments)
- Workflow: [`docs/workflows/investment-valuation.md`](../workflows/investment-valuation.md)
- User slices: 27-add-investment-holding, 28-add-fixed-deposit, 29-register-sip, 30-confirm-sip-detection, 31-view-portfolio, 32-view-portfolio-history, 41-edit-investment-holding

## Dependencies
- `identity` — JWT auth middleware
- `accounts` — publishes `AccountRemoved` which `investments` subscribes to (deactivates SIP registrations)
- `transactions` — publishes `TransactionCreated` which `investments` subscribes to (SIP detection)
- `fx` — `convert()` service method (portfolio total in INR)

## What to Build
Investment portfolio management across all Indian and international instrument types. Tracks what the user holds (`holdings`), what they paid (`avg_cost_per_unit`, `total_invested`), and what it is worth today (`current_value`). Valuations are kept current by two Temporal scheduled workflows — market-priced instruments via API calls every 15 minutes during market hours, calculated instruments (FD, PPF, bonds) daily. SIP auto-detection matches debit transactions against registered SIPs and notifies the user to confirm.

## Tables to Create
| Table | Key columns |
|---|---|
| `instruments` | `ticker`, `isin`, `name`, `type`, `exchange`, `currency`, `data_source`, `govt_rate_percent` |
| `holdings` | `user_id`, `instrument_id` FK→`instruments.id`, `units`, `avg_cost_per_unit`, `total_invested`, `current_value`, `current_price`, `last_valued_at` |
| `sip_registrations` | `user_id`, `instrument_id` FK→`instruments.id`, `amount`, `frequency`, `debit_day`, `bank_account_id` (no PG FK), `is_active` |
| `valuation_snapshots` | `holding_id` FK→`holdings.id`, `price`, `value`, `snapshot_date` |
| `fd_details` | `holding_id` FK→`holdings.id` UNIQUE, `principal`, `rate_percent`, `tenure_days`, `start_date`, `maturity_date`, `compounding`, `maturity_amount` |
| `investments_outbox` | standard outbox schema |

**Unique constraints**:
- `UNIQUE (user_id, instrument_id)` on `holdings` — one holding per instrument per user
- `UNIQUE (holding_id, snapshot_date)` on `valuation_snapshots` — one snapshot per holding per day (upserted)
- `UNIQUE (holding_id)` on `fd_details` — one FD detail per holding

`instruments.type` enum: `stock | mf | etf | fd | ppf | bond | nps | sgb | crypto | gold | us_stock | rd | other`
`sip_registrations.frequency` enum: `monthly | weekly | quarterly`
`fd_details.compounding` enum: `monthly | quarterly | annually | simple`

Note: `instruments` is a shared master registry (not per-user). Two users holding the same fund reference the same row. Price fetching runs once per instrument.

## Events Published
| Event | Consumed by |
|---|---|
| `investments.SIPDetected` | `notifications` — asks user to confirm SIP link |
| `investments.SIPLinked` | Audit only |
| `investments.ValuationUpdated` | Future: planning domain |

## Events Subscribed
| Event | Publisher | Handler behaviour |
|---|---|---|
| `accounts.AccountRemoved` | `accounts` | Set `is_active=false` on SIP registrations linked to that `bank_account_id` |
| `transactions.TransactionCreated` | `transactions` | Check debit against active SIP registrations; publish `SIPDetected` if match |

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/investments/instruments` | Search/list instruments (for adding a holding) |
| `POST` | `/investments/instruments` | Register a new instrument (admin or user-created lookup) |
| `GET` | `/investments/holdings` | List portfolio holdings with current value |
| `POST` | `/investments/holdings` | Add a holding |
| `PATCH` | `/investments/holdings/{id}` | Edit a holding (units, avg_cost, total_invested) |
| `DELETE` | `/investments/holdings/{id}` | Remove a holding |
| `POST` | `/investments/holdings/{holding_id}/fd` | Add FD details for an FD-type holding |
| `GET` | `/investments/history` | Historical portfolio value (aggregated `valuation_snapshots`) |
| `GET` | `/investments/sip` | List SIP registrations |
| `POST` | `/investments/sip` | Register a SIP |
| `PATCH` | `/investments/sip/{id}` | Edit a SIP registration |
| `DELETE` | `/investments/sip/{id}` | Deactivate a SIP |
| `POST` | `/investments/sip/{id}/confirm` | Confirm a SIP detection (from notification) |

## Action Steps

### Step 1 — Create `models.py`
Define `Instrument`, `Holding`, `SIPRegistration`, `ValuationSnapshot`, `FDDetails`, and `InvestmentsOutbox`.
- `Instrument`: `Base`, `IDMixin`, `MutableMixin` — shared table, no `user_id`
  - `type`: `CheckConstraint` for all 13 instrument types
  - `data_source`: nullable, `CheckConstraint` for `amfi | eodhd | coingecko | twelve_data | metals_api | calculated`
- `Holding`: `Base`, `IDMixin`, `MutableMixin`
  - `instrument_id`: FK to `instruments.id` (within-domain PG FK)
  - All `numeric` fields nullable — freshly added holdings may not have all details yet
- `SIPRegistration`: `Base`, `IDMixin`, `MutableMixin`
  - `bank_account_id`: nullable `uuid` (no PG FK — cross-domain reference)
  - `frequency`: `CheckConstraint`
- `ValuationSnapshot`: `Base`, `IDMixin`, `TimestampMixin` — immutable log (no `updated_at`)
  - `snapshot_date`: DATE, not null
- `FDDetails`: `Base`, `IDMixin`, `TimestampMixin` — immutable (FD terms don't change)
  - `compounding`: `CheckConstraint`

### Step 2 — Create Alembic migration
`uv run alembic revision --autogenerate -m "investments: add instruments, holdings, sip_registrations, valuation_snapshots, fd_details, investments_outbox"`.
Confirm unique constraints on `holdings(user_id, instrument_id)`, `valuation_snapshots(holding_id, snapshot_date)`, and `fd_details(holding_id)`.

### Step 3 — Create `repositories.py`
Key methods:
- `search_instruments(query, type_filter?) -> list[Instrument]` — ILIKE search on name and ticker
- `get_instrument_by_ticker(ticker) -> Instrument | None`
- `get_instrument_by_isin(isin) -> Instrument | None`
- `create_instrument(**fields) -> Instrument`
- `create_holding(user_id, instrument_id, **fields) -> Holding`
- `get_holding(user_id, holding_id) -> Holding | None`
- `get_holding_by_instrument(user_id, instrument_id) -> Holding | None` — for uniqueness check
- `list_holdings(user_id) -> list[Holding]` — with `Instrument` joined
- `update_holding(holding, **fields) -> Holding`
- `delete_holding(holding) -> None`
- `create_fd_details(holding_id, **fields) -> FDDetails`
- `get_fd_details(holding_id) -> FDDetails | None`
- `upsert_valuation_snapshot(holding_id, price, value, snapshot_date) -> None` — `INSERT ... ON CONFLICT (holding_id, snapshot_date) DO UPDATE`
- `list_snapshots_for_history(user_id, from_date, to_date) -> list[ValuationSnapshot]`
- `create_sip(user_id, instrument_id, **fields) -> SIPRegistration`
- `get_sip(user_id, sip_id) -> SIPRegistration | None`
- `list_sips(user_id, active_only=True) -> list[SIPRegistration]`
- `update_sip(sip, **fields) -> SIPRegistration`
- `deactivate_sips_for_account(account_id) -> None` — used by `AccountRemoved` handler

### Step 4 — Create `schemas.py`
- `InstrumentResponse`, `InstrumentCreate`
- `HoldingCreate` — instrument_id, units, avg_cost_per_unit, total_invested, current_price
- `HoldingUpdate` — units, avg_cost_per_unit, total_invested (all optional)
- `HoldingResponse` — includes instrument details and current_value
- `FDDetailsCreate` — principal, rate_percent, tenure_days, start_date, compounding
  - `maturity_date` and `maturity_amount` are computed server-side (not user input)
- `FDDetailsResponse`
- `SIPCreate` — instrument_id, amount, frequency, debit_day, bank_account_id (optional)
- `SIPUpdate` — amount, debit_day, is_active (all optional)
- `SIPResponse`
- `PortfolioHistoryPoint` — date, total_value (aggregated across holdings)
- `SIPConfirmRequest` — transaction_id, sip_registration_id

### Step 5 — Create `services.py`
- `search_instruments(query, type_filter?) -> list[InstrumentResponse]`
- `add_holding(user_id, data: HoldingCreate) -> HoldingResponse`
  - Validate `instrument_id` exists
  - Check `UNIQUE (user_id, instrument_id)` — reject duplicate with a clear error
- `edit_holding(user_id, holding_id, data: HoldingUpdate) -> HoldingResponse`
- `remove_holding(user_id, holding_id) -> None` — soft or hard delete (check with docs; hard delete is likely fine since `valuation_snapshots` cascade)
- `add_fd_details(user_id, holding_id, data: FDDetailsCreate) -> FDDetailsResponse`
  - Validate holding `instrument.type == 'fd'`
  - Compute `maturity_date = start_date + tenure_days`
  - Compute `maturity_amount = P * (1 + r/n)^(n*t)` at creation time
- `list_holdings(user_id) -> list[HoldingResponse]` — with current_value and instrument
- `get_portfolio_history(user_id, from_date, to_date) -> list[PortfolioHistoryPoint]`
  - Aggregate `valuation_snapshots.value` by `snapshot_date` across all of user's holdings
- `register_sip(user_id, data: SIPCreate) -> SIPResponse`
- `edit_sip(user_id, sip_id, data: SIPUpdate) -> SIPResponse`
- `deactivate_sip(user_id, sip_id) -> None`
- `confirm_sip_link(user_id, transaction_id, sip_id) -> None`
  - Validate ownership of both transaction and SIP
  - Write `SIPLinked` to outbox
- `_handle_transaction_created(transaction_id, user_id, account_id, amount, currency, date, type, session) -> None`
  - Skip if `type != 'debit'`
  - For each active SIP for user: check amount match (±2%) and date match (±3 days of `debit_day`) and `bank_account_id` match
  - If match: check idempotency (existing outbox row for `(transaction_id, sip_id)`); if not seen, write `SIPDetected` to outbox
- `_handle_account_removed(account_id, session) -> None`
  - Set `is_active=false` on all active SIPs with `bank_account_id = account_id` (idempotent)

### Step 6 — Create `events.py`
```python
@dataclass
class SIPDetected:
    event_type: ClassVar[str] = "investments.SIPDetected"
    transaction_id: UUID; user_id: UUID
    sip_registration_id: UUID; amount: Decimal; instrument_name: str

@dataclass
class SIPLinked:
    event_type: ClassVar[str] = "investments.SIPLinked"
    transaction_id: UUID; sip_registration_id: UUID; user_id: UUID

@dataclass
class ValuationUpdated:
    event_type: ClassVar[str] = "investments.ValuationUpdated"
    user_id: UUID; updated_holding_ids: list[UUID]; total_portfolio_value: Decimal
```

Event handlers:
```python
async def handle_account_removed(payload: dict, session: AsyncSession) -> None:
    # deactivate SIP registrations for removed account — idempotent

async def handle_transaction_created(payload: dict, session: AsyncSession) -> None:
    # check for SIP match — idempotent via outbox check
```

### Step 7 — Create Temporal workflows

#### `MarketPriceFetchWorkflow` (every 15 minutes during market hours)
Fetches live prices for: `stock`, `etf`, `mf`, `crypto`, `gold`, `us_stock`, `sgb`.
- Activity: get all distinct instrument IDs for these types
- Activity: fetch prices from appropriate API client per `data_source` field
- Activity: upsert `holdings.current_price`, `holdings.current_value = units * price`, `holdings.last_valued_at`
- Activity: upsert `valuation_snapshots` for today (one row per holding per day)
- Activity: publish `ValuationUpdated` event per user with updated holding IDs and portfolio total
- Activity: call `fx.convert()` for non-INR instruments to get INR total

#### `CalculatedValuationWorkflow` (daily at 00:30 IST)
Computes current value for `fd`, `rd`, `ppf`, `bond`, `nps`:
- Activity: get all holdings of these types with their `fd_details` / instrument details
- Activity: compute current value per formula (FD compound interest, PPF accumulation, bond accrued interest, etc.)
- Activity: upsert `holdings.current_value`, `holdings.last_valued_at`
- Activity: upsert `valuation_snapshots`

### Step 8 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.investments.events import handle_account_removed, handle_transaction_created
    event_bus.subscribe("accounts.AccountRemoved", handle_account_removed)
    event_bus.subscribe("transactions.TransactionCreated", handle_transaction_created)
    event_bus.register_outbox_table("investments_outbox")

def get_temporal_workflows() -> list:
    from elixir.domains.investments.workflows.market_price_fetch import MarketPriceFetchWorkflow
    from elixir.domains.investments.workflows.calculated_valuation import CalculatedValuationWorkflow
    return [MarketPriceFetchWorkflow, CalculatedValuationWorkflow]
```

### Step 9 — Register router and Temporal schedules in `runtime`
- Include `investments` router under prefix `/investments`
- Register `MarketPriceFetchWorkflow` on schedule (every 15 min, Mon–Fri, 09:00–15:30 IST)
- Register `CalculatedValuationWorkflow` on schedule (daily, 00:30 IST)

## Verification Checklist
- [ ] `UNIQUE (user_id, instrument_id)` prevents duplicate holdings — service returns 409
- [ ] FD details `maturity_amount` is computed server-side using the compound interest formula
- [ ] SIP detection: amount within ±2% AND date within ±3 days AND `bank_account_id` must all match
- [ ] `SIPDetected` idempotency: replaying `TransactionCreated` does not create duplicate outbox rows
- [ ] `AccountRemoved` handler sets all linked SIPs to `is_active=false` (idempotent)
- [ ] `valuation_snapshots` upsert: only one snapshot per holding per day
- [ ] Non-INR instrument values are converted to INR before aggregating portfolio total
- [ ] Ruff + mypy pass with no errors
