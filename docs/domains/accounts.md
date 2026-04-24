# Domain: accounts

## Responsibility

Provides named source labels for the user's bank accounts and credit cards. An account in Elixir is not a managed bank account — the application does not connect to banks, sync balances, or store statements after parsing. An account label exists for two purposes:

1. **Transaction source identification** — attaches a human-readable name (e.g. "HDFC Savings") and display metadata (bank, last4, currency) to transactions and statement uploads.
2. **Statement date range tracking** — records which date ranges have already been imported per account so the system can warn the user if a new upload overlaps a previously processed range.

The accounts domain does not track current balances. Balance views are never a responsibility of this domain.

---

## Tables Owned

### `bank_accounts`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | → `users.id` (no PG FK) |
| `nickname` | `text` NOT NULL | User-defined label e.g. "HDFC Savings", "SBI Joint" |
| `bank_name` | `text` NOT NULL | e.g. "HDFC Bank", "State Bank of India" |
| `account_type` | `text` NOT NULL | `savings` \| `current` \| `salary` \| `nre` \| `nro` |
| `last4` | `char(4)` | Last 4 digits of account number (display only) |
| `currency` | `char(3)` DEFAULT `'INR'` | Primary currency of this account |
| `is_active` | `bool` DEFAULT true | Soft-delete; inactive accounts are hidden from UI |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

Account numbers are never stored in full. `last4` is sufficient to identify which account the user means during statement upload or transaction review.

### `credit_cards`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | → `users.id` (no PG FK) |
| `nickname` | `text` NOT NULL | e.g. "HDFC Millennia", "Axis Flipkart" |
| `bank_name` | `text` NOT NULL | Issuing bank |
| `card_network` | `text` | `visa` \| `mastercard` \| `amex` \| `rupay` |
| `last4` | `char(4)` | Last 4 digits of card number |
| `credit_limit` | `numeric(15,2)` | Optional — used for utilisation display |
| `billing_cycle_day` | `int` | Day of month when the statement generates (1–28) |
| `currency` | `char(3)` DEFAULT `'INR'` | Primary billing currency |
| `is_active` | `bool` DEFAULT true | — |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

### `outbox`
Standard outbox table. See [data-model.md](../data-model.md).

---

## SQL Views Exposed

### `user_accounts_summary`
```sql
CREATE VIEW user_accounts_summary AS
SELECT
    id,
    user_id,
    nickname,
    bank_name,
    'bank' AS account_kind,
    account_type AS subtype,
    last4,
    currency,
    is_active
FROM bank_accounts
UNION ALL
SELECT
    id,
    user_id,
    nickname,
    bank_name,
    'credit_card' AS account_kind,
    card_network AS subtype,
    last4,
    currency,
    is_active
FROM credit_cards;
```

Used by `statements`, `transactions`, and `investments` to resolve account names for display without querying the accounts tables directly.

---

## Events Published

### `AccountLinked`
```python
@dataclass
class AccountLinked:
    event_type = "accounts.AccountLinked"
    account_id: UUID
    user_id: UUID
    account_kind: str  # 'bank' | 'credit_card'
    nickname: str
```
Consumed by: `notifications` — creates an onboarding nudge: *"Account added — upload a statement to start tracking transactions for this account."*

### `AccountRemoved`
```python
@dataclass
class AccountRemoved:
    event_type = "accounts.AccountRemoved"
    account_id: UUID
    user_id: UUID
    account_kind: str
```
Consumed by: `investments` — deactivates any `sip_registrations` where `bank_account_id = event.account_id`. SIP debit detection against a removed account is meaningless; deactivation prevents false-positive SIP alerts.

---

## Events Subscribed

None.

---

## Service Methods Exposed

None. Other domains reference accounts by ID only and read display metadata from the `user_accounts_summary` view.

---

Statement date-range overlap detection uses `account_id` as its grouping key but runs inside the `statements` domain's `StatementProcessingWorkflow`. See [domains/statements.md](statements.md) for details.

---

## Key Design Decisions

**Account labels are not managed bank connections.** The application does not sync live balances or connect to bank APIs. An account label is a user-created name for a transaction source, nothing more.

**Account numbers never stored in full.** Only `last4` is kept, for display purposes (e.g. "HDFC ···4521"). This limits the impact of a DB breach — there is no recoverable account number.

**No balance tracking in this domain.** Elixir is an expense and income tracker, not a balance reconciliation tool. Computing a "current balance" from transaction history is not a supported feature.

**`is_active` soft delete.** Deleting an account would orphan all linked transactions and statements (which reference `account_id`). Soft deletes preserve history while hiding the account from active UI. An account can only be hard-deleted if it has no linked transactions — enforced in the service layer.

**`billing_cycle_day` on credit cards.** This allows the budgets domain to align budget periods with the user's actual billing cycle (e.g., period runs 15th–14th if the card bills on the 15th), rather than forcing calendar months.
