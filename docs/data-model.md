# Data Model Overview

This document describes data ownership across domains, the cross-domain reference rules, and the key relationships between tables. It is not a full ERD — that lives in the Alembic migration files. This is a reference for understanding which domain owns what and how data flows between them.

---

## Domain Table Ownership

Each domain owns its tables exclusively. No other domain may write to them directly.

| Domain | Tables Owned |
|---|---|
| `identity` | `users`, `otp_requests`, `sessions`, `outbox` |
| `accounts` | `bank_accounts`, `credit_cards`, `outbox` |
| `statements` | `statement_uploads`, `extraction_jobs`, `raw_extracted_rows`, `outbox` |
| `transactions` | `transactions`, `transaction_items`, `outbox` |
| `categorization` | `categories`, `categorization_rules`, `outbox` |
| `earnings` | `earnings`, `earning_sources`, `outbox` |
| `investments` | `instruments`, `holdings`, `sip_registrations`, `valuation_snapshots`, `fd_details`, `outbox` |
| `budgets` | `budget_goals`, `budget_progress`, `budget_alerts`, `outbox` |
| `peers` | `peer_contacts`, `peer_balances`, `peer_settlements` |
| `notifications` | `notifications` |
| `fx` | `fx_rates` |
| `import_` | `import_jobs`, `import_column_mappings`, `outbox` |

Every domain that publishes events has its own `outbox` table. The schema is identical across domains:
```sql
outbox (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  text NOT NULL,
    payload     jsonb NOT NULL,
    status      text NOT NULL DEFAULT 'pending',  -- pending | processed | failed
    created_at  timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz
)
```

---

## Cross-Domain ID References

Domains reference each other's entities by ID only — no PostgreSQL foreign key constraints cross domain boundaries. Referential integrity is enforced at the application layer. This preserves domain isolation: the `transactions` table has no compile-time or runtime DB dependency on the `categorization` schema.

| Reference (from → to) | Column | Notes |
|---|---|---|
| `transactions.account_id` | → `bank_accounts.id` or `credit_cards.id` | Polymorphic: `account_type` column disambiguates |
| `transaction_items.category_id` | → `categories.id` | Category must exist for this user (enforced in service) |
| `transaction_items.transaction_id` | → `transactions.id` | Within-domain FK (has PG constraint) |
| `earnings.transaction_id` | → `transactions.id` | Nullable — earnings can be manually entered without a linked transaction |
| `holdings.instrument_id` | → `instruments.id` | Within-domain FK |
| `sip_registrations.bank_account_id` | → `bank_accounts.id` | Cross-domain: no PG FK |
| `budget_goals.category_id` | → `categories.id` | Cross-domain: no PG FK |
| `budget_alerts.goal_id` | → `budget_goals.id` | Within-domain FK |
| `peer_balances.peer_id` | → `peer_contacts.id` | Within-domain FK |
| `peer_settlements.balance_id` | → `peer_balances.id` | Within-domain FK |
| `fd_details.holding_id` | → `holdings.id` | Within-domain FK |
| `import_column_mappings.job_id` | → `import_jobs.id` | Within-domain FK |
| `raw_extracted_rows.job_id` | → `extraction_jobs.id` | Within-domain FK |
| `extraction_jobs.upload_id` | → `statement_uploads.id` | Within-domain FK |

---

## Key Table Schemas

### `transactions` + `transaction_items`

The core of the financial model. A single transaction (one line in a bank statement) can be split across multiple categories.

```
transactions
  id                uuid PK
  user_id           uuid (→ users.id, no FK)
  account_id        uuid (→ bank_accounts or credit_cards, no FK)
  account_type      text  -- 'bank' | 'credit_card'
  amount            numeric(15,2) NOT NULL
  currency          char(3) NOT NULL DEFAULT 'INR'
  date              date NOT NULL
  type              text NOT NULL  -- 'debit' | 'credit' | 'transfer'
  source            text NOT NULL  -- 'manual' | 'statement_import' | 'recurring_detected' | 'import'
  raw_description   text           -- original description from statement
  notes             text           -- user-added notes
  fingerprint       text           -- SHA-256 for deduplication; UNIQUE constraint is (user_id, fingerprint)
  created_at        timestamptz DEFAULT now()

transaction_items
  id                uuid PK
  transaction_id    uuid FK → transactions.id
  category_id       uuid (→ categories.id, no FK)
  amount            numeric(15,2) NOT NULL
  label             text           -- NULL means unlabelled under this category
  is_primary        bool DEFAULT false  -- true for the main category of a split
```

A transaction with no item-level breakdown has exactly one `transaction_items` row with `label = NULL`. A split transaction has multiple rows, amounts summing to `transactions.amount`.

### `holdings` + `valuation_snapshots`

```
holdings
  id                  uuid PK
  user_id             uuid
  instrument_id       uuid FK → instruments.id
  units               numeric(20,6)    -- for quantity-based instruments
  avg_cost_per_unit   numeric(15,4)
  total_invested      numeric(15,2)    -- actual cash put in
  current_value       numeric(15,2)    -- last computed value
  current_price       numeric(15,4)    -- last known price (market or calculated)
  last_valued_at      timestamptz

valuation_snapshots
  id                  uuid PK
  holding_id          uuid FK → holdings.id
  price               numeric(15,4)
  value               numeric(15,2)
  snapshot_date       date
  -- one row per holding per day; used for historical portfolio charts
  -- UNIQUE constraint: (holding_id, snapshot_date)
```

### `peer_balances` + `peer_settlements`

```
peer_balances
  id                uuid PK
  user_id           uuid
  peer_id           uuid FK → peer_contacts.id
  original_amount   numeric(15,2) NOT NULL
  settled_amount    numeric(15,2) NOT NULL DEFAULT 0
  remaining_amount  numeric(15,2) GENERATED ALWAYS AS (original_amount - settled_amount)
  direction         text NOT NULL  -- 'owed_to_me' | 'i_owe'
  status            text NOT NULL DEFAULT 'open'  -- 'open' | 'partial' | 'settled'
  created_at        timestamptz
  notes             text

peer_settlements
  id                uuid PK
  balance_id        uuid FK → peer_balances.id
  amount            numeric(15,2) NOT NULL
  settled_at        timestamptz NOT NULL
  notes             text
```

`remaining_amount` is a generated column — it always equals `original_amount - settled_amount`. `status` is updated by the application after each settlement.

---

## SQL Views Exposed by Each Domain

These views are the only cross-domain read interface. Other domains query these by name — never the underlying tables.

| View Name | Defined by domain | Purpose |
|---|---|---|
| `users_public` | `identity` | `(id, name)` — strips phone number |
| `user_accounts_summary` | `accounts` | All accounts (bank + credit card) for a user |
| `categories_for_user` | `categorization` | Default categories + user's custom categories merged |
| `transactions_with_categories` | `transactions` | Transactions joined with items and category names |
| `peer_contacts_public` | `peers` | `(id, user_id, name)` — used by `earnings` to match credit descriptions against known peer names |

### Note on `categories_for_user`

This view exposes default categories with `user_id = NULL`. Callers must filter with `WHERE user_id = :uid OR user_id IS NULL` to receive both the user's custom categories and the system defaults. A plain `WHERE user_id = :uid` will return only custom categories and silently exclude all defaults.

---

## Common Columns

Every domain table includes these columns from the SQLAlchemy base mixin (`shared/base.py`):

```python
id         = Column(UUID, primary_key=True, default=uuid4)
created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Tables that represent mutable user data also include:

```python
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

Tables that are mutable but whose schemas omit `updated_at` for a documented reason must note that reason in their domain doc. Tables confirmed to require `updated_at`: `transactions`, `transaction_items`, `peer_balances`, `peer_contacts`, `instruments`, `holdings`, `sip_registrations`, `categories`, `categorization_rules`, `budget_goals`, `earning_sources`.

---

## Data Integrity Rules

1. **No cross-domain PostgreSQL foreign keys.** Referential integrity is the application's responsibility.
2. **Every row is user-scoped.** All queries must include a `WHERE user_id = :user_id` clause. PostgreSQL RLS enforces this at the DB level as a safety net.
3. **Amounts are always `numeric(15,2)`.** Never float. Financial precision is non-negotiable.
4. **Currency stored alongside amount.** Every `amount` column has a sibling `currency char(3)` column. Never assume INR.
5. **Fingerprints for deduplication.** The `transactions.fingerprint` column (SHA-256 of normalised date + description + amount) prevents double-importing the same transaction. The unique constraint is composite: `UNIQUE (user_id, fingerprint)`. Two different users may have identical-looking transactions; their fingerprints must not collide.
6. **Transfer transactions are excluded from budget and earnings tracking.** Any transaction with `type = 'transfer'` is a self-transfer between the user's own accounts. Budget handlers and earnings handlers must skip these rows. A transaction may be marked as `transfer` by automatic detection or by the user manually.
7. **Budget spend is in the currency of the transaction, converted to the goal currency.** `budget_progress.current_spend` accumulates amounts converted to the goal's `currency` at the FX rate active at the time of the `TransactionCategorized` event. Never add raw foreign-currency amounts to an INR budget without conversion.
