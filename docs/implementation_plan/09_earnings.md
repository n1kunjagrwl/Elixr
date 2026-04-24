# Implementation Plan: earnings

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/earnings.md`](../domains/earnings.md)
- Data model: [`docs/data-model.md`](../data-model.md#earnings)
- User slices: 21-classify-ambiguous-credit, 22-add-manual-earning, 23-manage-earning-sources, 38-view-earnings-dashboard, 39-edit-earning, 45-filter-earnings-by-source

## Dependencies
- `identity` — JWT auth middleware
- `transactions` — publishes `TransactionCreated` which `earnings` subscribes to
- `peers` — `peer_contacts_public` view (queried during credit classification heuristics)

Both `transactions` and `peers` must be running before `earnings` event handlers can function correctly.

## What to Build
Tracks all income the user receives. Credits from bank statements are inspected automatically: high-confidence income (salary patterns, employer keywords) creates an `earnings` record; high-confidence peer repayments are skipped; ambiguous credits trigger an `EarningClassificationNeeded` notification. Users can also manually log income (cash earnings, foreign transfers, etc.) and manage named earning sources (e.g., "Think41 Salary").

## Tables to Create
| Table | Key columns |
|---|---|
| `earning_sources` | `user_id`, `name`, `type`, `is_active` |
| `earnings` | `user_id`, `transaction_id` (nullable, no PG FK), `source_id` (nullable, no PG FK), `source_type`, `source_label`, `amount`, `currency`, `date`, `notes` |
| `earnings_outbox` | standard outbox schema |

`source_type` enum: `salary | freelance | rental | dividend | interest | business | other`

Note: `source_type` is stored on `earnings` redundantly from `earning_sources` — intentional so aggregation by income type works even when `source_id` is NULL or the source has been deleted.

## Events Published
| Event | Consumed by |
|---|---|
| `earnings.EarningRecorded` | Audit only |
| `earnings.EarningClassificationNeeded` | `notifications` — prompts user to classify ambiguous credit |

## Events Subscribed
| Event | Publisher | Handler behaviour |
|---|---|---|
| `transactions.TransactionCreated` | `transactions` | Inspect credit transactions; auto-create or ask user |

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/earnings` | List earnings (filterable by source_type, date range) |
| `POST` | `/earnings` | Add a manual earning |
| `PATCH` | `/earnings/{id}` | Edit an earning (source, notes, date, amount) |
| `POST` | `/earnings/classify/{transaction_id}` | Classify an ambiguous credit (income type / peer repayment / ignore) |
| `GET` | `/earnings/sources` | List earning sources |
| `POST` | `/earnings/sources` | Add a new earning source |
| `PATCH` | `/earnings/sources/{id}` | Edit a source (name, type, is_active) |
| `DELETE` | `/earnings/sources/{id}` | Deactivate a source |

## Action Steps

### Step 1 — Create `models.py`
Define `EarningSource`, `Earning`, and `EarningsOutbox`.
- `EarningSource`: `Base`, `IDMixin`, `MutableMixin`
- `Earning`: `Base`, `IDMixin`, `MutableMixin`
  - `transaction_id`: nullable `uuid` (no PG FK — cross-domain reference to `transactions.id`)
  - `source_id`: nullable `uuid` (no PG FK — within-domain reference, but nullable)
  - `source_type`: `CheckConstraint` for the 7 values

### Step 2 — Create Alembic migration
`uv run alembic revision --autogenerate -m "earnings: add earning_sources, earnings, earnings_outbox"`.

### Step 3 — Create `repositories.py`
Key methods:
- `create_source(user_id, name, source_type) -> EarningSource`
- `list_sources(user_id, active_only=True) -> list[EarningSource]`
- `get_source(user_id, source_id) -> EarningSource | None`
- `update_source(source, **fields) -> EarningSource`
- `create_earning(user_id, **fields) -> Earning`
- `get_earning(user_id, earning_id) -> Earning | None`
- `get_earning_by_transaction(user_id, transaction_id) -> Earning | None` — idempotency check in event handler
- `list_earnings(user_id, source_type?, date_from?, date_to?, source_id?) -> list[Earning]`
- `update_earning(earning, **fields) -> Earning`

### Step 4 — Create `schemas.py`
- `EarningSourceCreate` — name, type
- `EarningSourceUpdate` — name, type, is_active (all optional)
- `EarningSourceResponse`
- `EarningCreate` — amount, currency, date, source_type, source_id (optional), source_label (optional), notes (optional)
  - Validate: either `source_id` or `source_label` must be present (or neither for bare `other` entries)
- `EarningUpdate` — amount, currency, date, source_id, source_label, notes, source_type (all optional)
- `EarningResponse` — includes source details
- `ClassifyTransactionRequest` — classification: `income` | `peer_repayment` | `ignore`; source_type (if `income`); source_id (optional); notes (optional)

### Step 5 — Create `services.py`
- `list_sources(user_id) -> list[EarningSourceResponse]`
- `add_source(user_id, data) -> EarningSourceResponse`
- `edit_source(user_id, source_id, data) -> EarningSourceResponse`
- `deactivate_source(user_id, source_id) -> None`
- `add_manual_earning(user_id, data: EarningCreate) -> EarningResponse`
  - `transaction_id = None` (manual)
  - Write `EarningRecorded` to outbox in same transaction
- `edit_earning(user_id, earning_id, data: EarningUpdate) -> EarningResponse`
- `classify_transaction(user_id, transaction_id, data: ClassifyTransactionRequest) -> None`
  - If `income`: create `Earning` record linked to `transaction_id`; write `EarningRecorded` to outbox
  - If `peer_repayment`: do nothing (peers domain handles this independently)
  - If `ignore`: mark the classification as resolved without creating an earnings record
    (store a record in `earnings` with `source_type='other'` and a `source_label='ignored'`? Or a separate ignore flag? — ask before implementing if unclear)
- `list_earnings(user_id, filters) -> list[EarningResponse]`

- `_handle_transaction_created(transaction_id, user_id, amount, currency, description, type, session) -> None`
  - Called by the event handler (not directly by API)
  - Skip if `type != 'credit'` or `type == 'transfer'`
  - Check if `earnings` record already exists for this `transaction_id` — if yes, skip (idempotency)
  - Run heuristics:
    1. Pattern match: SALARY, NEFT, IMPS, employer name patterns → high-confidence income
    2. Recurring match: same amount ±5%, similar day of month as existing salary earning
    3. Peer name match: query `peer_contacts_public` view with `WHERE user_id = :user_id` and check if description contains any peer name
  - Score ≥ 0.85 income → create `Earning`, write `EarningRecorded` to outbox
  - Score ≥ 0.85 peer repayment → skip
  - Ambiguous → write `EarningClassificationNeeded` to outbox

### Step 6 — Create `events.py`
```python
@dataclass
class EarningRecorded:
    event_type: ClassVar[str] = "earnings.EarningRecorded"
    earning_id: UUID; user_id: UUID; source_type: str
    amount: Decimal; currency: str; date: date

@dataclass
class EarningClassificationNeeded:
    event_type: ClassVar[str] = "earnings.EarningClassificationNeeded"
    transaction_id: UUID; user_id: UUID
    amount: Decimal; currency: str; description: str
```

Event handler (subscribed):
```python
async def handle_transaction_created(payload: dict, session: AsyncSession) -> None:
    # delegates to EarningsService._handle_transaction_created
    # idempotency: check existing earnings record for transaction_id before creating
```

### Step 7 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.earnings.events import handle_transaction_created
    event_bus.subscribe("transactions.TransactionCreated", handle_transaction_created)
    event_bus.register_outbox_table("earnings_outbox")

def get_temporal_workflows() -> list:
    return []

def get_temporal_activities(*args) -> list:
    return []
```

### Step 8 — Complete `api.py`
8 endpoints. Error mappings:
- `EarningNotFoundError` → 404
- `EarningSourceNotFoundError` → 404
- `TransactionAlreadyClassifiedError` → 409

### Step 9 — Register router in `runtime/app.py`
Include the `earnings` router under prefix `/earnings`.

## Verification Checklist
- [ ] A salary credit (NEFT from employer) auto-creates an `Earning` record without user action
- [ ] An ambiguous credit creates an `EarningClassificationNeeded` outbox event (not a direct earning)
- [ ] `POST /earnings/classify/{transaction_id}` with `income` creates the `Earning` and writes `EarningRecorded`
- [ ] Handler is idempotent: replaying `TransactionCreated` does not create duplicate earnings
- [ ] `transaction_id = NULL` is valid for manually-added earnings
- [ ] `source_type` is always stored on `Earning`, even when `source_id` is NULL
- [ ] Transfer transactions (`type='transfer'`) are skipped — never create earnings records
- [ ] Peer name check queries `peer_contacts_public` view with correct `user_id` filter
- [ ] Ruff + mypy pass with no errors
