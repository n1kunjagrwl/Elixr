# Implementation Plan: transactions

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/transactions.md`](../domains/transactions.md)
- Data model: [`docs/data-model.md`](../data-model.md#transactions)
- Workflow: [`docs/workflows/recurring-detection.md`](../workflows/recurring-detection.md)
- User slices: 15-add-transaction-manually, 16-edit-transaction, 44-browse-search-transactions

## Dependencies
- `identity` — JWT auth middleware
- `categorization` — `categories_for_user` view (validates `category_id` on `transaction_items`)
- `accounts` — `user_accounts_summary` view (resolves account display name)
- `statements` — publishes `ExtractionCompleted` and `ExtractionPartiallyCompleted` which `transactions` subscribes to
- `import_` — publishes `ImportBatchReady` which `transactions` subscribes to

Note: `statements` and `import_` can be implemented after `transactions` is complete, since the event handlers in `transactions` just need to be registered at bootstrap time.

## What to Build
The source of truth for all financial movements. Stores transactions and their item-level category breakdown (2-level model). Transactions enter via three paths: statement extraction events, import batch events, or manual entry via API. Publishes `TransactionCreated`, `TransactionCategorized`, and `TransactionUpdated` events which downstream domains (`earnings`, `investments`, `budgets`) react to. Exposes `transactions_with_categories` SQL view for cross-domain aggregation reads.

## Tables to Create
| Table | Key columns |
|---|---|
| `transactions` | `user_id`, `account_id`, `account_kind`, `amount`, `currency`, `date`, `type`, `source`, `raw_description`, `notes`, `fingerprint`, `created_at`, `updated_at` |
| `transaction_items` | `transaction_id` FK→`transactions.id`, `category_id` (no PG FK), `amount`, `currency`, `label`, `is_primary`, `updated_at` |
| `transactions_outbox` | standard outbox schema |

**Unique constraint**: `UNIQUE (user_id, fingerprint)` on `transactions`. Manual entries have `fingerprint = NULL` and are exempt.

`type` enum: `debit | credit | transfer`
`source` enum: `manual | statement_import | recurring_detected | bulk_import`

Fingerprint formula: `SHA-256(lower(trim(raw_description)) + date.isoformat() + str(amount))` — computed in the service layer, never in the DB.

## SQL View to Create
```sql
CREATE VIEW transactions_with_categories AS
SELECT
    t.id, t.user_id, t.account_id, t.account_kind, t.amount, t.currency,
    t.date, t.type, t.source, t.raw_description, t.notes,
    ti.id AS item_id, ti.category_id, ti.amount AS item_amount,
    ti.currency AS item_currency, ti.label, ti.is_primary
FROM transactions t
JOIN transaction_items ti ON ti.transaction_id = t.id;
```
Consumers: `earnings`, `budgets` (aggregation queries — never query `transactions` or `transaction_items` directly).

## Events Published
| Event | Consumed by |
|---|---|
| `transactions.TransactionCreated` | `earnings`, `investments`, `budgets` |
| `transactions.TransactionCategorized` | `budgets` |
| `transactions.TransactionUpdated` | `budgets` |

## Events Subscribed
| Event | Publisher | Handler behaviour |
|---|---|---|
| `statements.ExtractionCompleted` | `statements` | Create transactions from `classified_rows`; check fingerprint for duplicates; publish `TransactionCreated` + `TransactionCategorized` per row |
| `statements.ExtractionPartiallyCompleted` | `statements` | Same handler — processes `classified_rows` only |
| `import_.ImportBatchReady` | `import_` | Same handler — creates transactions from `rows` payload with `source='bulk_import'` |

**All event handlers must be idempotent.** Check `(user_id, fingerprint)` before inserting. If a row already exists, skip it silently.

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/transactions` | List/search/filter transactions (paginated) |
| `GET` | `/transactions/{id}` | Get a single transaction with items |
| `POST` | `/transactions` | Add a manual transaction |
| `PATCH` | `/transactions/{id}` | Edit a transaction (notes, type, items/categories) |

## Action Steps

### Step 1 — Create `models.py`
Define `Transaction`, `TransactionItem`, and `TransactionsOutbox`.
- `Transaction`: `Base`, `IDMixin`, `MutableMixin`
  - `type`: `CheckConstraint` for `debit | credit | transfer`
  - `source`: `CheckConstraint` for `manual | statement_import | recurring_detected | bulk_import`
  - `fingerprint`: nullable (NULL for manual entries); unique constraint is `UNIQUE (user_id, fingerprint)` — requires partial unique index `WHERE fingerprint IS NOT NULL` to allow multiple NULL fingerprints per user
  - `account_kind`: `CheckConstraint` for `bank | credit_card`
- `TransactionItem`: `Base`, `IDMixin`, `MutableMixin`
  - FK to `Transaction` (within-domain PG FK with `ondelete="CASCADE"`)
  - `category_id`: `uuid` with no PG FK (cross-domain reference)

### Step 2 — Create Alembic migration for tables
`uv run alembic revision --autogenerate -m "transactions: add transactions, transaction_items, transactions_outbox"`.
Manually add the partial unique index on `(user_id, fingerprint) WHERE fingerprint IS NOT NULL` — autogenerate will not create this.

### Step 3 — Create Alembic migration for `transactions_with_categories` view
Separate migration: `uv run alembic revision -m "transactions: add transactions_with_categories view"`.

### Step 4 — Create `repositories.py`
Key methods:
- `create_transaction(user_id, **fields) -> Transaction`
- `create_transaction_items(transaction_id, items: list[dict]) -> list[TransactionItem]`
- `get_transaction(user_id, transaction_id) -> Transaction | None`
- `list_transactions(user_id, filters: TransactionFilters, page, page_size) -> Page[Transaction]`
  - Filters: date_from, date_to, account_id, type, source, category_id (via JOIN with items), search_text (pg_trgm or ILIKE on raw_description)
- `update_transaction(transaction, **fields) -> Transaction`
- `replace_transaction_items(transaction_id, items: list[dict]) -> list[TransactionItem]` — delete all existing items then insert new ones
- `fingerprint_exists(user_id, fingerprint) -> bool`
- `find_potential_transfers(user_id, amount, currency, date, account_id) -> list[Transaction]` — for transfer auto-detection post-import

### Step 5 — Create `schemas.py`
- `TransactionCreate` — account_id, account_kind, amount, currency, date, type, raw_description, notes, items (list of `{category_id, amount, label}`)
  - Minimum one item required
  - Item amounts must sum to transaction amount
- `TransactionUpdate` — notes (optional), type (optional), items (optional)
- `TransactionItemSchema` — category_id, amount, currency, label, is_primary
- `TransactionResponse` — full transaction with items
- `TransactionSummary` — paginated list item (no items detail)
- `TransactionFilters` — date_from, date_to, account_id, type, source, category_id, search_text

### Step 6 — Create `services.py`
- `add_transaction(user_id, data: TransactionCreate, session) -> TransactionResponse`
  - Source = `manual`; fingerprint = None (manual entries exempt from deduplication)
  - Validate all `category_id` values are visible to user (query `categories_for_user` view)
  - Validate item amounts sum to transaction amount
  - Write `TransactionCreated` and `TransactionCategorized` to outbox in same transaction
- `edit_transaction(user_id, transaction_id, data: TransactionUpdate, session) -> TransactionResponse`
  - If items changed: validate amounts sum; replace items; write `TransactionUpdated` to outbox with `old_items` and `new_items`
  - If type changed to/from `transfer`: update category accordingly
- `list_transactions(user_id, filters, page, page_size) -> Page[TransactionSummary]`
- `get_transaction(user_id, transaction_id) -> TransactionResponse`
- `create_transactions_from_classified_rows(user_id, account_id, account_kind, rows: list[dict], source: str, session) -> None`
  - Called by the `ExtractionCompleted` / `ImportBatchReady` event handlers
  - For each row: compute fingerprint; skip if exists; insert transaction + items; write `TransactionCreated` + `TransactionCategorized` to outbox
  - Run transfer auto-detection after all rows are inserted (within same service call)
- `_detect_transfers(user_id, new_transaction_ids: list[UUID], session) -> None`
  - For each new transaction: look for counterpart within ±2 days, exact amount, opposite type, different account
  - If found: update both to `type='transfer'`, assign "Self Transfer" category, emit SSE notification

### Step 7 — Create `events.py`
```python
@dataclass
class TransactionCreated:
    event_type: ClassVar[str] = "transactions.TransactionCreated"
    transaction_id: UUID; user_id: UUID; account_id: UUID
    amount: Decimal; currency: str; date: date; type: str; source: str

@dataclass
class TransactionCategorized:
    event_type: ClassVar[str] = "transactions.TransactionCategorized"
    transaction_id: UUID; user_id: UUID
    items: list[dict]  # [{category_id, amount, currency, label}]

@dataclass
class TransactionUpdated:
    event_type: ClassVar[str] = "transactions.TransactionUpdated"
    transaction_id: UUID; user_id: UUID; date: date
    changed_fields: list[str]
    old_items: list[dict] | None
    new_items: list[dict] | None
```

Event handlers (subscribed from other domains):
```python
async def handle_extraction_completed(payload: dict, session: AsyncSession) -> None:
    # create transactions from classified_rows — idempotent via fingerprint check

async def handle_extraction_partially_completed(payload: dict, session: AsyncSession) -> None:
    # same handler as ExtractionCompleted — processes classified_rows only

async def handle_import_batch_ready(payload: dict, session: AsyncSession) -> None:
    # create transactions from rows — source='bulk_import' — same idempotency pattern
```

### Step 8 — Create Temporal workflow `workflows/recurring_detection.py`
Scheduled: weekly, Sunday 02:00 IST.

```
RecurringTransactionDetectionWorkflow.run():
  1. Activity: get_all_user_ids() → list[UUID]
  2. For each user_id:
     Activity: scan_for_recurring(user_id, lookback_days=90)
       - Get all debit transactions for user in last 90 days
       - Group by normalised merchant description (lower(trim(raw_description)))
       - For each group with >= 2 occurrences: check for consistent interval (daily/weekly/monthly)
       - For confirmed recurring clusters: update transaction.source = 'recurring_detected'
       - Publish one SSE notification per cluster (not per transaction)
```

This workflow does not create new transactions. It only relabels existing ones.

### Step 9 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.transactions.events import (
        handle_extraction_completed,
        handle_extraction_partially_completed,
        handle_import_batch_ready,
    )
    event_bus.subscribe("statements.ExtractionCompleted", handle_extraction_completed)
    event_bus.subscribe("statements.ExtractionPartiallyCompleted", handle_extraction_partially_completed)
    event_bus.subscribe("import_.ImportBatchReady", handle_import_batch_ready)
    event_bus.register_outbox_table("transactions_outbox")

def get_temporal_workflows() -> list:
    from elixir.domains.transactions.workflows.recurring_detection import RecurringTransactionDetectionWorkflow
    return [RecurringTransactionDetectionWorkflow]
```

### Step 10 — Register router in `runtime/app.py`
Include the `transactions` router under prefix `/transactions`.

## Verification Checklist
- [ ] `POST /transactions` creates transaction + items in a single DB transaction with outbox rows
- [ ] Importing the same statement twice skips duplicate fingerprints silently
- [ ] Transfer auto-detection sets `type='transfer'` on both sides (debit + credit)
- [ ] `PATCH /transactions/{id}` with new items writes `TransactionUpdated` with `old_items` and `new_items`
- [ ] `GET /transactions` filters work correctly (date range, account, category, search text)
- [ ] `transactions_with_categories` view is queryable
- [ ] Pagination returns correct `total` count and respects `page_size`
- [ ] Transfer transactions (`type='transfer'`) are not counted by budget or earnings handlers (enforcement in those domains, but confirm the `type` field is included in all relevant events)
- [ ] Ruff + mypy pass with no errors
