# Implementation Plan: peers

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/peers.md`](../domains/peers.md)
- Data model: [`docs/data-model.md`](../data-model.md#peers)
- User slices: 33-add-peer-contact, 34-log-peer-balance, 35-record-peer-settlement, 40-edit-delete-peer-contact

## Dependencies
- `identity` — all queries filter by `user_id`.
- No other domain dependencies.

## What to Build
A manual ledger for tracking money owed to/from peers (friends, family, colleagues). Pure CRUD — no event-driven behaviour, no external integrations, no Temporal workflows. The domain exposes a `peer_contacts_public` SQL view consumed by `earnings` during credit classification. Settlements are append-only — corrections are new rows, not edits.

## Tables to Create
| Table | Key columns |
|---|---|
| `peer_contacts` | `user_id`, `name`, `phone` (nullable), `notes` (nullable) |
| `peer_balances` | `user_id`, `peer_id` FK→`peer_contacts.id`, `description`, `original_amount`, `settled_amount`, `remaining_amount` (generated), `currency`, `direction`, `status`, `linked_transaction_id` (nullable, no PG FK) |
| `peer_settlements` | `balance_id` FK→`peer_balances.id`, `amount`, `currency`, `settled_at`, `method` (nullable), `linked_transaction_id` (nullable, no PG FK), `notes` |

**Generated column**: `remaining_amount NUMERIC(15,2) GENERATED ALWAYS AS (original_amount - settled_amount) STORED` on `peer_balances`. PostgreSQL generates this — never compute it in Python.

**No outbox table** — `peers` publishes no domain events.

## SQL View to Create
```sql
CREATE VIEW peer_contacts_public AS
SELECT id, user_id, name FROM peer_contacts;
```
Consumer: `earnings` — queries this view filtered by `user_id` to detect peer names in credit descriptions.

## Events Published
None.

## Events Subscribed
None.

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/peers/contacts` | List all peer contacts for the user |
| `POST` | `/peers/contacts` | Add a new peer contact |
| `PATCH` | `/peers/contacts/{id}` | Edit peer contact (name, phone, notes) |
| `DELETE` | `/peers/contacts/{id}` | Delete a peer contact (only if no open balances) |
| `GET` | `/peers/balances` | List peer balances (filterable by status: open, partial, settled) |
| `POST` | `/peers/balances` | Log a new peer balance |
| `PATCH` | `/peers/balances/{id}` | Edit a balance (description, notes; not amount — use settlement for that) |
| `GET` | `/peers/balances/{id}/settlements` | List settlements for a balance |
| `POST` | `/peers/balances/{id}/settlements` | Record a settlement |

## Action Steps

### Step 1 — Create `models.py`
Define `PeerContact`, `PeerBalance`, and `PeerSettlement` models.
- `PeerContact`: `Base`, `IDMixin`, `MutableMixin`
- `PeerBalance`: `Base`, `IDMixin`, `MutableMixin`
  - `remaining_amount`: use SQLAlchemy `Computed` column — `Computed("original_amount - settled_amount", persisted=True)`
  - `direction`: `CheckConstraint` for `owed_to_me | i_owe`
  - `status`: `CheckConstraint` for `open | partial | settled`
  - `peer_id`: FK to `peer_contacts.id` (within-domain PG FK)
- `PeerSettlement`: `Base`, `IDMixin`, `TimestampMixin` (immutable — no `updated_at`)
  - `method`: nullable, `CheckConstraint` for `cash | upi | bank_transfer | other`
  - `balance_id`: FK to `peer_balances.id` (within-domain PG FK)

### Step 2 — Create Alembic migration for tables
`uv run alembic revision --autogenerate -m "peers: add peer_contacts, peer_balances, peer_settlements"`.
Check that the `GENERATED ALWAYS AS` expression for `remaining_amount` is rendered correctly. SQLAlchemy's autogenerate may not handle computed columns correctly — verify the migration SQL manually and edit if needed.

### Step 3 — Create Alembic migration for `peer_contacts_public` view
Separate migration: `uv run alembic revision -m "peers: add peer_contacts_public view"`.

### Step 4 — Create `repositories.py`
Key methods:
- `create_contact(user_id, name, phone?, notes?) -> PeerContact`
- `get_contact(user_id, contact_id) -> PeerContact | None`
- `list_contacts(user_id) -> list[PeerContact]`
- `update_contact(contact, **fields) -> PeerContact`
- `delete_contact(contact) -> None`
- `has_open_balances(contact_id) -> bool` — guard for delete
- `create_balance(user_id, peer_id, **fields) -> PeerBalance`
- `get_balance(user_id, balance_id) -> PeerBalance | None`
- `list_balances(user_id, status_filter?) -> list[PeerBalance]`
- `update_balance(balance, **fields) -> PeerBalance`
- `create_settlement(balance_id, **fields) -> PeerSettlement`
  - Also updates `balance.settled_amount += settlement.amount` and recomputes `balance.status` in the same operation
- `list_settlements(balance_id) -> list[PeerSettlement]`

### Step 5 — Create `schemas.py`
- `PeerContactCreate`, `PeerContactUpdate`, `PeerContactResponse`
- `PeerBalanceCreate` — peer_id, description, original_amount, currency, direction, linked_transaction_id (optional), notes (optional)
- `PeerBalanceUpdate` — description, notes (both optional)
- `PeerBalanceResponse` — includes `remaining_amount` (read from DB generated column)
- `PeerSettlementCreate` — amount, currency, settled_at, method (optional), linked_transaction_id (optional), notes (optional)
- `PeerSettlementResponse`

### Step 6 — Create `services.py`
- `add_contact(user_id, data) -> PeerContactResponse`
- `edit_contact(user_id, contact_id, data) -> PeerContactResponse`
- `delete_contact(user_id, contact_id) -> None`
  - Reject if `has_open_balances` — return a clear error message
- `log_balance(user_id, data) -> PeerBalanceResponse`
  - Validate `peer_id` belongs to this user
- `edit_balance(user_id, balance_id, data) -> PeerBalanceResponse`
- `record_settlement(user_id, balance_id, data) -> PeerSettlementResponse`
  - Validate `settlement.amount <= balance.remaining_amount` — a settlement cannot exceed what remains
  - Update `settled_amount` and recalculate `status` (`open→partial` or `partial/open→settled` when `remaining_amount = 0`)
  - Note: `remaining_amount` itself is a generated column in PG — always read it from DB after the update
- `list_balances(user_id, status_filter?) -> list[PeerBalanceResponse]`
- `list_settlements(user_id, balance_id) -> list[PeerSettlementResponse]`

### Step 7 — Create `events.py`
No events. File contains only a module docstring:
```python
# peers domain publishes no events and subscribes to none.
# PeerContact names are exposed cross-domain via the peer_contacts_public SQL view (Pattern 1).
```

### Step 8 — Complete `api.py`
9 endpoints. Error mappings:
- `PeerContactNotFoundError` → 404
- `PeerBalanceNotFoundError` → 404
- `ContactHasOpenBalancesError` → 409 (cannot delete contact with open balances)
- `SettlementExceedsRemainingError` → 422

### Step 9 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    pass  # peers has no outbox, no subscriptions

def get_temporal_workflows() -> list:
    return []

def get_temporal_activities(*args) -> list:
    return []
```

### Step 10 — Register router in `runtime/app.py`
Include the `peers` router under prefix `/peers`.

## Verification Checklist
- [ ] `remaining_amount` is always read from the DB generated column — never recomputed in Python
- [ ] Recording a settlement updates `settled_amount` and `status` correctly (`open→partial→settled`)
- [ ] Settlement amount > `remaining_amount` returns 422 (cannot over-settle)
- [ ] Deleting a contact with open balances returns 409
- [ ] `peer_contacts_public` view exposes only `id`, `user_id`, `name` (no phone)
- [ ] All queries filter by `user_id`
- [ ] Settlements are never edited — only new settlement rows are appended
- [ ] Ruff + mypy pass with no errors
