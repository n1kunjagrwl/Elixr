# Implementation Plan: accounts

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/accounts.md`](../domains/accounts.md)
- Data model: [`docs/data-model.md`](../data-model.md#accounts)
- User slices: 05-add-bank-account, 06-add-credit-card, 07-edit-account, 08-deactivate-account

## Dependencies
- `identity` must be complete — every query filters by `user_id` from the JWT middleware.

## What to Build
Named source labels for bank accounts and credit cards. Accounts are not managed bank connections — no live balance sync, no bank API. The domain exists to give transactions and statements a human-readable source name, and to enable date-range overlap detection for statement uploads. Publishes `AccountLinked` and `AccountRemoved` events.

## Tables to Create
| Table | Key columns |
|---|---|
| `bank_accounts` | `user_id`, `nickname`, `bank_name`, `account_type`, `last4`, `currency`, `is_active` |
| `credit_cards` | `user_id`, `nickname`, `bank_name`, `card_network`, `last4`, `credit_limit`, `billing_cycle_day`, `currency`, `is_active` |
| `accounts_outbox` | standard outbox schema (see data-model.md) |

## SQL View to Create
```sql
CREATE VIEW user_accounts_summary AS
SELECT id, user_id, nickname, bank_name,
       'bank' AS account_kind, account_type AS subtype, last4, currency, is_active
FROM bank_accounts
UNION ALL
SELECT id, user_id, nickname, bank_name,
       'credit_card' AS account_kind, card_network AS subtype, last4, currency, is_active
FROM credit_cards;
```
Consumers: `statements`, `transactions` (display-only, never writes to accounts tables).

## Events Published
| Event | Consumed by |
|---|---|
| `accounts.AccountLinked` | `notifications` — onboarding nudge |
| `accounts.AccountRemoved` | `investments` — deactivate linked SIP registrations |

## Events Subscribed
None.

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/accounts` | List all active accounts (bank + credit cards) for the authenticated user |
| `POST` | `/accounts/bank` | Add a bank account |
| `POST` | `/accounts/credit-cards` | Add a credit card |
| `PATCH` | `/accounts/bank/{id}` | Edit bank account details (nickname, last4, etc.) |
| `PATCH` | `/accounts/credit-cards/{id}` | Edit credit card details |
| `DELETE` | `/accounts/bank/{id}` | Deactivate a bank account (soft delete — sets `is_active = false`) |
| `DELETE` | `/accounts/credit-cards/{id}` | Deactivate a credit card |

## Action Steps

### Step 1 — Create `models.py`
Define `BankAccount`, `CreditCard`, and `AccountsOutbox` SQLAlchemy models.
- Inherit `Base`, `IDMixin`, `MutableMixin` from `shared/base.py` for `BankAccount` and `CreditCard`
- Inherit `Base`, `IDMixin`, `TimestampMixin` for `AccountsOutbox`
- `account_type` on `BankAccount`: use a `CheckConstraint` for the enum values `savings | current | salary | nre | nro`
- `card_network` on `CreditCard`: nullable; `CheckConstraint` for `visa | mastercard | amex | rupay`
- No cross-domain PG foreign keys — `user_id` references `users.id` in application logic only
- `last4` is `CHAR(4)` nullable

### Step 2 — Create Alembic migration for tables
Run `uv run alembic revision --autogenerate -m "accounts: add bank_accounts, credit_cards, accounts_outbox"`.
Review generated SQL — add the `CHECK` constraints manually if autogenerate omits them. One migration file per domain (this one covers accounts tables only).

### Step 3 — Create Alembic migration for `user_accounts_summary` view
Separate migration file: `uv run alembic revision -m "accounts: add user_accounts_summary view"`.
Write the `CREATE VIEW` SQL manually in `upgrade()` and `DROP VIEW IF EXISTS` in `downgrade()`.

### Step 4 — Create `repositories.py`
All methods take `AsyncSession` and return ORM models or primitives. Filter every query by `user_id`.

Key methods:
- `create_bank_account(user_id, **fields) -> BankAccount`
- `create_credit_card(user_id, **fields) -> CreditCard`
- `get_bank_account(user_id, account_id) -> BankAccount | None`
- `get_credit_card(user_id, card_id) -> CreditCard | None`
- `list_accounts(user_id, active_only=True) -> list[BankAccount | CreditCard]` (queries the `user_accounts_summary` view via raw SQL)
- `update_bank_account(account, **fields) -> BankAccount`
- `update_credit_card(card, **fields) -> CreditCard`
- `deactivate_bank_account(account) -> None` (sets `is_active = false`)
- `deactivate_credit_card(card) -> None`
- `has_linked_transactions(account_id) -> bool` (raw SQL count against `transactions` via cross-domain read — pattern 3 justified: hard-delete guard)

### Step 5 — Create `schemas.py`
Pydantic v2 models. Never expose ORM models via API.

- `BankAccountCreate` — request body for `POST /accounts/bank`
- `CreditCardCreate` — request body for `POST /accounts/credit-cards`
- `BankAccountUpdate` — PATCH body (all fields optional)
- `CreditCardUpdate` — PATCH body (all fields optional)
- `BankAccountResponse` — response (excludes `user_id`; includes `id`, `nickname`, `bank_name`, `account_type`, `last4`, `currency`, `is_active`, `created_at`)
- `CreditCardResponse` — response
- `AccountSummaryResponse` — flattened view response (from `user_accounts_summary`)

### Step 6 — Create `services.py`
Business logic only. No HTTP concerns.

- `add_bank_account(user_id, data: BankAccountCreate) -> BankAccountResponse`
  - Creates row, writes `AccountLinked` to `accounts_outbox` in same transaction
- `add_credit_card(user_id, data: CreditCardCreate) -> CreditCardResponse`
  - Same pattern as above
- `edit_bank_account(user_id, account_id, data: BankAccountUpdate) -> BankAccountResponse`
  - Fetch + validate ownership + update
- `edit_credit_card(user_id, card_id, data: CreditCardUpdate) -> CreditCardResponse`
- `deactivate_bank_account(user_id, account_id) -> None`
  - Check `has_linked_transactions` — if true, only soft-delete (`is_active = false`). Write `AccountRemoved` to outbox in same transaction.
  - Hard-delete is only allowed when no linked transactions exist (guard enforced in service).
- `deactivate_credit_card(user_id, card_id) -> None`
- `list_accounts(user_id) -> list[AccountSummaryResponse]`
  - Query `user_accounts_summary` view

### Step 7 — Create `events.py`
Define event dataclasses and outbox handler functions.

```python
@dataclass
class AccountLinked:
    event_type: ClassVar[str] = "accounts.AccountLinked"
    account_id: UUID
    user_id: UUID
    account_kind: str  # 'bank' | 'credit_card'
    nickname: str

@dataclass
class AccountRemoved:
    event_type: ClassVar[str] = "accounts.AccountRemoved"
    account_id: UUID
    user_id: UUID
    account_kind: str
```

Handler stubs (these handlers have no subscribers in this domain — they are consumed by `notifications` and `investments`):
```python
async def handle_account_linked(payload: dict, session: AsyncSession) -> None:
    pass  # no-op: accounts does not subscribe to its own events

async def handle_account_removed(payload: dict, session: AsyncSession) -> None:
    pass  # no-op
```

### Step 8 — Complete `api.py`
Create the `APIRouter` with all 7 endpoints. Use `Depends` for `AsyncSession` and `user_id` (from the auth middleware token). Map service exceptions to HTTP status codes:
- `AccountNotFoundError` → 404
- `AccountBelongsToAnotherUserError` → 403
- `AccountHasLinkedTransactionsError` → 409 (cannot hard-delete)

### Step 9 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    event_bus.register_outbox_table("accounts_outbox")

def get_temporal_workflows() -> list:
    return []  # no workflows in accounts domain

def get_temporal_activities(*args) -> list:
    return []
```
No event subscriptions — `accounts` only publishes.

### Step 10 — Register router in `runtime/app.py`
Include the `accounts` router under prefix `/accounts`. Confirm the existing `app.py` pattern from `identity` and follow the same include pattern.

## Verification Checklist
- [ ] `POST /accounts/bank` creates a row and an `accounts_outbox` row in the same transaction
- [ ] Deactivating an account with transactions sets `is_active = false` (not DELETE)
- [ ] `user_accounts_summary` view returns both bank and credit card rows in a single query
- [ ] All queries filter by `user_id` — no cross-user data leakage
- [ ] `last4` is stored as-is (4 chars) — no full account number is accepted or stored
- [ ] `AccountLinked` and `AccountRemoved` are written to outbox atomically with the business operation
- [ ] Ruff + mypy pass with no errors
