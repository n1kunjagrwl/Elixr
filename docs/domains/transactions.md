# Domain: transactions

## Responsibility

The source of truth for all financial movements in the system. Every debit, credit, and transfer that Elixir knows about lives here — whether it came from a statement upload, an import, or manual entry. The transactions domain does not make categorisation decisions; it stores the results of categorisation and exposes them for querying. It owns the 2-level breakdown model: a transaction is split into one or more `transaction_items`, each belonging to a category, with an optional item-level label.

---

## Tables Owned

### `transactions`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `account_id` | `uuid` NOT NULL | → `bank_accounts.id` or `credit_cards.id` (no PG FK) |
| `account_kind` | `text` NOT NULL | `bank` \| `credit_card` |
| `amount` | `numeric(15,2)` NOT NULL | Total transaction amount |
| `currency` | `char(3)` NOT NULL DEFAULT `'INR'` | — |
| `date` | `date` NOT NULL | Transaction date |
| `type` | `text` NOT NULL | `debit` \| `credit` \| `transfer` |
| `source` | `text` NOT NULL | `manual` \| `statement_import` \| `recurring_detected` \| `bulk_import` |
| `raw_description` | `text` | Original description as it appeared on the statement |
| `notes` | `text` | User-added notes |
| `fingerprint` | `text` UNIQUE per `user_id` | SHA-256 of normalised `date + description + amount` — prevents duplicate imports |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

### `transaction_items`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `transaction_id` | `uuid` FK → `transactions.id` | — |
| `category_id` | `uuid` NOT NULL | → `categories.id` (no PG FK) |
| `amount` | `numeric(15,2)` NOT NULL | Portion of the transaction in this category |
| `label` | `text` | Item name e.g. "Butter Chicken", "Monthly Netflix". NULL = unlabelled |
| `is_primary` | `bool` DEFAULT false | True for the first/main category when a transaction is split |

**The 2-level model in practice:**

```
Scenario A — Simple transaction, one category, no item breakdown
  transaction: amount=500, description="Swiggy"
  transaction_items: [{category="Food & Dining", amount=500, label=NULL, is_primary=true}]

Scenario B — Simple transaction, one category, with item breakdown
  transaction: amount=500, description="Swiggy"
  transaction_items: [
    {category="Food & Dining", amount=250, label="Butter Chicken", is_primary=true},
    {category="Food & Dining", amount=150, label="Naan x2"},
    {category="Food & Dining", amount=100, label="Delivery fee"},
  ]

Scenario C — Split transaction, multiple categories
  transaction: amount=2000, description="Amazon"
  transaction_items: [
    {category="Shopping", amount=1200, label="Headphones", is_primary=true},
    {category="Groceries", amount=800, label="Olive oil"}
  ]
```

### `outbox`
Standard outbox table. See [data-model.md](../data-model.md).

---

## SQL Views Exposed

### `transactions_with_categories`
```sql
CREATE VIEW transactions_with_categories AS
SELECT
    t.id,
    t.user_id,
    t.account_id,
    t.account_kind,
    t.amount,
    t.currency,
    t.date,
    t.type,
    t.source,
    t.raw_description,
    t.notes,
    ti.id AS item_id,
    ti.category_id,
    ti.amount AS item_amount,
    ti.label,
    ti.is_primary
FROM transactions t
JOIN transaction_items ti ON ti.transaction_id = t.id;
```

Used by the `earnings` and `budgets` domains for aggregation queries.

---

## Events Published

### `TransactionCreated`
```python
@dataclass
class TransactionCreated:
    event_type = "transactions.TransactionCreated"
    transaction_id: UUID
    user_id: UUID
    account_id: UUID
    amount: Decimal
    currency: str
    date: date
    type: str       # 'debit' | 'credit' | 'transfer'
    source: str
```
Consumed by: `earnings` (credit classification), `investments` (SIP detection), `budgets` (budget tracking)

### `TransactionCategorized`
```python
@dataclass
class TransactionCategorized:
    event_type = "transactions.TransactionCategorized"
    transaction_id: UUID
    user_id: UUID
    items: list[dict]  # [{category_id, amount, label}]
```
Published when items are first written or subsequently updated. Consumed by: `budgets`

### `TransactionUpdated`
```python
@dataclass
class TransactionUpdated:
    event_type = "transactions.TransactionUpdated"
    transaction_id: UUID
    user_id: UUID
    changed_fields: list[str]
```
Published when the user edits a transaction's category breakdown or notes.

---

## Events Subscribed

### `ExtractionCompleted` (from `statements`)

When a statement processing job finishes, the transactions domain creates `transaction` and `transaction_items` records from the classified rows payload. Each row maps to one `transactions` row plus one or more `transaction_items` rows.

Handler must be idempotent: check `fingerprint` before inserting. If a row with the same fingerprint already exists for this user, skip it.

---

## Service Methods Exposed

None. Other domains read from the `transactions_with_categories` view.

---

## Key Design Decisions

**`transaction_items` instead of a single category column.** A single `category_id` on the transaction itself cannot model split transactions (one Amazon order = electronics + groceries). The items table makes this a first-class feature.

**`label = NULL` for unlabelled items.** When a user selects "Food & Dining" for an ₹800 Swiggy order without specifying what they ate, one item row is created with `label = NULL`. The transaction is still categorised and trackable; it simply lacks item-level detail. This is better than requiring item detail that the user may not want to provide.

**`fingerprint` for deduplication.** SHA-256 of `lower(trim(description)) + date.isoformat() + str(amount)`. Prevents a user from accidentally importing the same statement twice and creating duplicate transactions.

**`source` field for provenance.** Knowing whether a transaction came from a statement, a manual entry, or recurring detection matters for display (show a different icon) and for analytics (how complete is this user's data?).
