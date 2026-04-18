# Domain: accounts

## Responsibility

Manages the financial accounts a user registers in Elixir — bank accounts and credit cards. An account represents a real-world account the user holds at a financial institution. It is the anchor for uploaded statements and logged transactions. The accounts domain does not hold balances or transaction history — it only holds metadata needed to identify and label an account.

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

### `AccountRemoved`
```python
@dataclass
class AccountRemoved:
    event_type = "accounts.AccountRemoved"
    account_id: UUID
    user_id: UUID
    account_kind: str
```

---

## Events Subscribed

None.

---

## Service Methods Exposed

None. Other domains reference accounts by ID only and read display metadata from the `user_accounts_summary` view.

---

## Key Design Decisions

**Account numbers never stored in full.** Only `last4` is kept, for display purposes (e.g. "HDFC ···4521"). This limits the impact of a DB breach — there is no recoverable account number.

**No balance tracking in this domain.** The current balance of an account is always computed from the transaction history in the `transactions` domain. Storing a balance here would create a second source of truth that could drift.

**`is_active` soft delete.** Deleting an account would orphan all linked transactions and statements (which reference `account_id`). Soft deletes preserve history while hiding the account from active UI. An account can only be hard-deleted if it has no linked transactions — enforced in the service layer.

**`billing_cycle_day` on credit cards.** This allows the budgets domain to align budget periods with the user's actual billing cycle (e.g., budget period runs 15th–14th if the card bills on the 15th), rather than forcing calendar months.
