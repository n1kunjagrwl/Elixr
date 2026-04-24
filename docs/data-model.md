# Data Model

This document is the authoritative reference for table and view ownership across all 12 domains. It defines every column, every cross-domain reference, and every key constraint. It does not contain business logic — that lives in `docs/domains/`. It does not contain migration SQL — that lives in Alembic.

---

## Quick Reference — Domain Ownership

| Domain | Tables | Views |
|---|---|---|
| `identity` | `users`, `otp_requests`, `sessions`, `outbox` | `users_public` |
| `accounts` | `bank_accounts`, `credit_cards`, `outbox` | `user_accounts_summary` |
| `statements` | `statement_uploads`, `extraction_jobs`, `raw_extracted_rows`, `raw_row_items`, `outbox` | — |
| `transactions` | `transactions`, `transaction_items`, `outbox` | `transactions_with_categories` |
| `categorization` | `categories`, `categorization_rules`, `outbox` | `categories_for_user` |
| `earnings` | `earning_sources`, `earnings`, `outbox` | — |
| `investments` | `instruments`, `holdings`, `sip_registrations`, `valuation_snapshots`, `fd_details`, `outbox` | — |
| `budgets` | `budget_goals`, `budget_progress`, `budget_alerts`, `outbox` | — |
| `peers` | `peer_contacts`, `peer_balances`, `peer_settlements` | `peer_contacts_public` |
| `notifications` | `notifications` | — |
| `fx` | `fx_rates` | — |
| `import_` | `import_jobs`, `import_column_mappings`, `import_row_errors`, `outbox` | — |

---

## Common Schema

### Outbox Table

Every domain that publishes events owns an `outbox` table with this schema. The table name is qualified by domain in Alembic (e.g., `identity_outbox`) but accessed as `outbox` within each domain's SQLAlchemy models.

| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK DEFAULT `gen_random_uuid()` | — |
| `event_type` | `text` NOT NULL | e.g. `identity.UserRegistered` |
| `payload` | `jsonb` NOT NULL | Serialised event dataclass — varies per event type |
| `status` | `text` NOT NULL DEFAULT `'pending'` | `pending` \| `processed` \| `failed` |
| `created_at` | `timestamptz` NOT NULL DEFAULT `now()` | — |
| `processed_at` | `timestamptz` NULLABLE | Set when status → `processed` |
| `attempt_count` | `int` NOT NULL DEFAULT 0 | Incremented on each dispatch attempt |
| `last_error` | `text` NULLABLE | Final exception message when status → `failed` |

`payload` is the only justified `jsonb` column in the schema. Event structures vary per type and are consumed only by the EventBus dispatcher — they are never queried by domain logic. All other `jsonb` columns from earlier drafts have been normalised into dedicated tables or typed columns (see `raw_row_items`, `import_row_errors`, and the notifications table below).

**Status lifecycle**: `pending` → `processed` on successful dispatch; `pending` → `failed` after `MAX_OUTBOX_ATTEMPTS` (default 5) failed attempts. Failed rows require manual intervention. The health check reports `degraded` if any outbox has `pending` rows older than 30 seconds or any `failed` rows.

**At-least-once delivery**: Every event handler must be idempotent. The narrow window between dispatch and marking `processed` can cause the same event to be dispatched more than once on server restart.

### Column Conventions

Every table inherits these two columns from the SQLAlchemy base mixin (`shared/base.py`):

| Column | Type | Applied to |
|---|---|---|
| `id` | `uuid` PK DEFAULT `gen_random_uuid()` | All tables |
| `created_at` | `timestamptz` NOT NULL DEFAULT `now()` | All tables |

Tables representing mutable records also include:

| Column | Type | Applied to |
|---|---|---|
| `updated_at` | `timestamptz` NULLABLE `ON UPDATE now()` | `users`, `bank_accounts`, `credit_cards`, `transactions`, `transaction_items`, `categories`, `categorization_rules`, `earnings`, `earning_sources`, `instruments`, `holdings`, `sip_registrations`, `peer_contacts`, `peer_balances`, `budget_goals`, `budget_progress` |

Tables that are immutable logs (`budget_alerts`, `peer_settlements`, `valuation_snapshots`, `raw_extracted_rows`, `raw_row_items`, `import_column_mappings`, `import_row_errors`, `otp_requests`, `sessions`, `fx_rates`) do not have `updated_at`.

---

## Per-Domain Schemas

---

### identity

#### `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | Internal identifier |
| `phone_e164` | `text` | NOT NULL UNIQUE | E.164 format e.g. `+919876543210` |
| `name` | `text` | NULLABLE | Display name |
| `created_at` | `timestamptz` | NOT NULL | — |

#### `otp_requests`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | → `users.id` (within-domain FK) |
| `code_hash` | `text` | NOT NULL | bcrypt hash of the 6-digit OTP |
| `expires_at` | `timestamptz` | NOT NULL | `now() + 60 seconds` |
| `attempt_count` | `int` | NOT NULL DEFAULT 0 | Incremented on each failed verification |
| `locked_until` | `timestamptz` | NULLABLE | Set to `now() + 5 minutes` after 3 failed attempts |
| `delivered` | `bool` | NOT NULL DEFAULT false | True once Twilio confirms SMS delivery |
| `created_at` | `timestamptz` | NOT NULL | — |

#### `sessions`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | → `users.id` (within-domain FK) |
| `access_token_jti` | `uuid` | UNIQUE | JWT ID of the active access token |
| `refresh_token_jti` | `uuid` | UNIQUE | JWT ID of the active refresh token |
| `expires_at` | `timestamptz` | NOT NULL | Refresh token expiry (7 days from creation) |
| `revoked_at` | `timestamptz` | NULLABLE | Set on logout — null means active |
| `created_at` | `timestamptz` | NOT NULL | — |

#### Views

```sql
CREATE VIEW users_public AS
SELECT id, name FROM users;
```

Used by: any domain that needs to display a user name. Phone is never exposed outside the identity domain.

---

### accounts

#### `bank_accounts`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | → `users.id` (no PG FK) |
| `nickname` | `text` | NOT NULL | User-defined label e.g. "HDFC Savings" |
| `bank_name` | `text` | NOT NULL | e.g. "HDFC Bank" |
| `account_type` | `text` | NOT NULL | `savings` \| `current` \| `salary` \| `nre` \| `nro` |
| `last4` | `char(4)` | NULLABLE | Last 4 digits of account number (display only) |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | Primary currency |
| `is_active` | `bool` | NOT NULL DEFAULT true | Soft-delete flag |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

Full account numbers are never stored. `last4` is sufficient for display and identification during upload.

#### `credit_cards`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | → `users.id` (no PG FK) |
| `nickname` | `text` | NOT NULL | e.g. "HDFC Millennia" |
| `bank_name` | `text` | NOT NULL | Issuing bank |
| `card_network` | `text` | NULLABLE | `visa` \| `mastercard` \| `amex` \| `rupay` |
| `last4` | `char(4)` | NULLABLE | Last 4 digits of card number |
| `credit_limit` | `numeric(15,2)` | NULLABLE | For utilisation display |
| `billing_cycle_day` | `int` | NULLABLE | Day of month when statement generates (1–28) |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | Primary billing currency |
| `is_active` | `bool` | NOT NULL DEFAULT true | Soft-delete flag |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### Views

```sql
CREATE VIEW user_accounts_summary AS
SELECT
    id, user_id, nickname, bank_name,
    'bank'       AS account_kind,
    account_type AS subtype,
    last4, currency, is_active
FROM bank_accounts
UNION ALL
SELECT
    id, user_id, nickname, bank_name,
    'credit_card' AS account_kind,
    card_network  AS subtype,
    last4, currency, is_active
FROM credit_cards;
```

Used by: `statements`, `transactions` — resolves account display name and kind without querying accounts tables directly.

---

### statements

#### `statement_uploads`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `account_id` | `uuid` | NOT NULL | → `bank_accounts.id` or `credit_cards.id` (no PG FK) |
| `account_kind` | `text` | NOT NULL | `bank` \| `credit_card` |
| `file_path` | `text` | NOT NULL | User-scoped storage path; deleted after parsing completes |
| `file_type` | `text` | NOT NULL | `pdf` \| `csv` |
| `original_filename` | `text` | NULLABLE | As uploaded, for display |
| `period_start` | `date` | NULLABLE | Earliest transaction date found; set by parsing activity |
| `period_end` | `date` | NULLABLE | Latest transaction date found; set by parsing activity |
| `status` | `text` | NOT NULL DEFAULT `'uploaded'` | `uploaded` \| `processing` \| `completed` \| `partial` \| `failed` |
| `uploaded_at` | `timestamptz` | NOT NULL | — |

#### `extraction_jobs`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `upload_id` | `uuid` | NOT NULL FK → `statement_uploads.id` | — |
| `temporal_workflow_id` | `text` | NULLABLE | Temporal run ID; used to send signals |
| `status` | `text` | NOT NULL DEFAULT `'queued'` | `queued` \| `parsing` \| `classifying` \| `awaiting_input` \| `completed` \| `partial` \| `failed` |
| `total_rows` | `int` | NULLABLE | Set after parsing |
| `classified_rows` | `int` | NOT NULL DEFAULT 0 | Incremented as rows are classified |
| `error_message` | `text` | NULLABLE | Populated if status = `failed` |
| `created_at` | `timestamptz` | NOT NULL | — |
| `completed_at` | `timestamptz` | NULLABLE | — |

#### `raw_extracted_rows`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `job_id` | `uuid` | NOT NULL FK → `extraction_jobs.id` | — |
| `row_index` | `int` | NOT NULL | Original position in statement (for ordering) |
| `date` | `date` | NULLABLE | Transaction date parsed from statement |
| `description` | `text` | NULLABLE | Raw description from statement |
| `debit_amount` | `numeric(15,2)` | NULLABLE | Null if credit row |
| `credit_amount` | `numeric(15,2)` | NULLABLE | Null if debit row |
| `balance` | `numeric(15,2)` | NULLABLE | Running balance from statement (if available) |
| `classification_status` | `text` | NOT NULL DEFAULT `'pending'` | `pending` \| `auto_classified` \| `user_classified` \| `skipped` |
| `ai_suggested_category_id` | `uuid` | NULLABLE | ADK suggestion (no PG FK) |
| `ai_confidence` | `float` | NULLABLE | 0.0–1.0 |
| `final_category_id` | `uuid` | NULLABLE | Set on user confirmation (no PG FK) |
| `transaction_id` | `uuid` | NULLABLE | Set when row is committed as a transaction (no PG FK) |
| `created_at` | `timestamptz` | NOT NULL | — |

#### `raw_row_items`

Normalised replacement for the former `raw_extracted_rows.final_items jsonb` column. Stores the user-provided item breakdown for a raw row when the user classifies a statement row with item-level detail.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `row_id` | `uuid` | NOT NULL FK → `raw_extracted_rows.id` | — |
| `label` | `text` | NULLABLE | Item name e.g. "Butter Chicken"; NULL = unlabelled |
| `amount` | `numeric(15,2)` | NOT NULL | Item amount |
| `created_at` | `timestamptz` | NOT NULL | — |

Item amounts across all `raw_row_items` for a given `row_id` must sum to the row's debit or credit amount — enforced in the service layer, not the DB.

---

### transactions

#### `transactions`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `account_id` | `uuid` | NOT NULL | → `bank_accounts.id` or `credit_cards.id` (no PG FK) |
| `account_kind` | `text` | NOT NULL | `bank` \| `credit_card` |
| `amount` | `numeric(15,2)` | NOT NULL | Total transaction amount |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | — |
| `date` | `date` | NOT NULL | Transaction date |
| `type` | `text` | NOT NULL | `debit` \| `credit` \| `transfer` |
| `source` | `text` | NOT NULL | `manual` \| `statement_import` \| `recurring_detected` \| `bulk_import` |
| `raw_description` | `text` | NULLABLE | Original description from statement |
| `notes` | `text` | NULLABLE | User-added notes |
| `fingerprint` | `text` | NULLABLE | SHA-256(`lower(trim(description)) + date.isoformat() + str(amount)`) |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

**Unique constraint**: `UNIQUE (user_id, fingerprint)`. Manual entries (source = `manual`) have `fingerprint = NULL` and are exempt from deduplication.

#### `transaction_items`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `transaction_id` | `uuid` | NOT NULL FK → `transactions.id` | — |
| `category_id` | `uuid` | NOT NULL | → `categories.id` (no PG FK) |
| `amount` | `numeric(15,2)` | NOT NULL | Portion of the transaction in this category |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | Matches the parent transaction's currency |
| `label` | `text` | NULLABLE | Item name e.g. "Butter Chicken"; NULL = unlabelled |
| `is_primary` | `bool` | NOT NULL DEFAULT false | True for the main category of a split transaction |
| `updated_at` | `timestamptz` | NULLABLE | — |

Item amounts across all rows for a given `transaction_id` must sum to `transactions.amount` — enforced in the service layer.

**2-level model**: a simple uncategorised transaction has one item row with `label = NULL`. A split transaction has multiple rows summing to the parent amount.

#### Views

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
    ti.id          AS item_id,
    ti.category_id,
    ti.amount      AS item_amount,
    ti.currency    AS item_currency,
    ti.label,
    ti.is_primary
FROM transactions t
JOIN transaction_items ti ON ti.transaction_id = t.id;
```

Used by: `earnings`, `budgets` — aggregation queries on spend and income. Never queries the underlying tables directly.

---

### categorization

#### `categories`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NULLABLE | NULL for system-seeded defaults; set for user-created categories |
| `name` | `text` | NOT NULL | Display name e.g. "Food & Dining" |
| `slug` | `text` | NOT NULL | URL-safe identifier e.g. `food-dining` |
| `kind` | `text` | NOT NULL | `expense` \| `income` \| `transfer` |
| `parent_id` | `uuid` | NULLABLE FK → `categories.id` | Reserved for sub-categories (future use) |
| `icon` | `text` | NULLABLE | Emoji or icon identifier |
| `is_default` | `bool` | NOT NULL DEFAULT false | True for system-seeded rows |
| `is_active` | `bool` | NOT NULL DEFAULT true | Users can hide custom categories they never use |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

Default categories have `user_id = NULL` and are shared across all users. A unique constraint on `(slug, user_id)` prevents duplicate slugs per user (NULL user_id is treated as its own partition).

#### `categorization_rules`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | Rules are always user-specific |
| `pattern` | `text` | NOT NULL | Text to match against `raw_description` |
| `match_type` | `text` | NOT NULL | `contains` \| `starts_with` \| `exact` \| `regex` |
| `category_id` | `uuid` | NOT NULL | → `categories.id` (no PG FK) |
| `priority` | `int` | NOT NULL DEFAULT 0 | Higher values checked first |
| `is_active` | `bool` | NOT NULL DEFAULT true | — |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### Views

```sql
CREATE VIEW categories_for_user AS
SELECT id, name, slug, kind, icon, is_default, parent_id, NULL::uuid AS user_id
FROM categories
WHERE user_id IS NULL AND is_active = true
UNION ALL
SELECT id, name, slug, kind, icon, is_default, parent_id, user_id
FROM categories
WHERE user_id IS NOT NULL AND is_active = true;
```

**Critical filter rule**: Callers must use `WHERE user_id = :uid OR user_id IS NULL` to receive both system defaults and user custom categories. A plain `WHERE user_id = :uid` silently omits all defaults.

---

### earnings

#### `earning_sources`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `name` | `text` | NOT NULL | e.g. "Think41 Salary", "Freelance — Acme Corp" |
| `type` | `text` | NOT NULL | `salary` \| `freelance` \| `rental` \| `dividend` \| `interest` \| `business` \| `other` |
| `is_active` | `bool` | NOT NULL DEFAULT true | Inactive sources hidden from manual entry dropdowns |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### `earnings`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `transaction_id` | `uuid` | NULLABLE | → `transactions.id` (no PG FK); NULL for manually-entered earnings |
| `source_id` | `uuid` | NULLABLE | → `earning_sources.id` (no PG FK); NULL if source not categorised |
| `source_type` | `text` | NOT NULL | `salary` \| `freelance` \| `rental` \| `dividend` \| `interest` \| `business` \| `other` |
| `source_label` | `text` | NULLABLE | Free-text label used when `source_id` is NULL |
| `amount` | `numeric(15,2)` | NOT NULL | — |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | — |
| `date` | `date` | NOT NULL | — |
| `notes` | `text` | NULLABLE | — |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

`source_type` is stored redundantly from the linked `earning_sources` row to allow aggregation by income type even when `source_id` is NULL or the source has been deleted.

---

### investments

#### `instruments`

Shared master registry — not per-user. Two users holding the same fund reference the same row.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `ticker` | `text` | NULLABLE | NSE/BSE symbol, AMFI scheme code, CoinGecko ID, or internal ID |
| `isin` | `text` | NULLABLE | ISIN code where applicable |
| `name` | `text` | NOT NULL | Full name e.g. "HDFC Top 100 Fund — Growth" |
| `type` | `text` | NOT NULL | `stock` \| `mf` \| `etf` \| `fd` \| `ppf` \| `bond` \| `nps` \| `sgb` \| `crypto` \| `gold` \| `us_stock` \| `rd` \| `other` |
| `exchange` | `text` | NULLABLE | `NSE` \| `BSE` \| `NYSE` \| `NASDAQ` \| `MCX` |
| `currency` | `char(3)` | NOT NULL | Primary trading currency |
| `data_source` | `text` | NULLABLE | Which API client provides prices: `amfi` \| `eodhd` \| `coingecko` \| `twelve_data` \| `metals_api` \| `calculated` |
| `govt_rate_percent` | `numeric(6,3)` | NULLABLE | Current government-declared rate for PPF/NPS |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### `holdings`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `instrument_id` | `uuid` | NOT NULL FK → `instruments.id` | — |
| `units` | `numeric(20,6)` | NULLABLE | Quantity held (6 decimal places for MF units) |
| `avg_cost_per_unit` | `numeric(15,4)` | NULLABLE | Weighted average cost |
| `total_invested` | `numeric(15,2)` | NULLABLE | Total cash invested |
| `current_value` | `numeric(15,2)` | NULLABLE | Last computed value = `units × current_price` |
| `current_price` | `numeric(15,4)` | NULLABLE | Last known price per unit |
| `last_valued_at` | `timestamptz` | NULLABLE | When `current_value` was last updated |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

**Unique constraint**: `UNIQUE (user_id, instrument_id)`. A user can hold each instrument only once; adding more units requires editing the existing holding, not creating a new row.

#### `sip_registrations`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `instrument_id` | `uuid` | NOT NULL FK → `instruments.id` | Which fund/stock this SIP is for |
| `amount` | `numeric(15,2)` | NOT NULL | Expected debit amount per instalment |
| `frequency` | `text` | NOT NULL | `monthly` \| `weekly` \| `quarterly` |
| `debit_day` | `int` | NULLABLE | Day of month for monthly SIPs (1–31) |
| `bank_account_id` | `uuid` | NULLABLE | → `bank_accounts.id` (no PG FK) |
| `is_active` | `bool` | NOT NULL DEFAULT true | Set false when the linked bank account is removed |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### `valuation_snapshots`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `holding_id` | `uuid` | NOT NULL FK → `holdings.id` | — |
| `price` | `numeric(15,4)` | NOT NULL | Price per unit at snapshot time |
| `value` | `numeric(15,2)` | NOT NULL | Total holding value at snapshot time |
| `snapshot_date` | `date` | NOT NULL | — |
| `created_at` | `timestamptz` | NOT NULL | — |

**Unique constraint**: `UNIQUE (holding_id, snapshot_date)`. One snapshot per holding per day; upserted by the valuation workflow.

#### `fd_details`

Supplementary detail for holdings with `instruments.type = 'fd'`. One row per FD holding.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `holding_id` | `uuid` | NOT NULL FK → `holdings.id` UNIQUE | One FD detail row per holding |
| `principal` | `numeric(15,2)` | NOT NULL | Amount deposited |
| `rate_percent` | `numeric(6,3)` | NOT NULL | Annual interest rate |
| `tenure_days` | `int` | NOT NULL | Total FD tenure in days |
| `start_date` | `date` | NOT NULL | FD opening date |
| `maturity_date` | `date` | NOT NULL | `start_date + tenure_days` |
| `compounding` | `text` | NOT NULL | `monthly` \| `quarterly` \| `annually` \| `simple` |
| `maturity_amount` | `numeric(15,2)` | NULLABLE | Computed at creation: `P × (1 + r/n)^(n×t)` |
| `created_at` | `timestamptz` | NOT NULL | — |

---

### budgets

#### `budget_goals`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `category_id` | `uuid` | NOT NULL | → `categories.id` (no PG FK) |
| `limit_amount` | `numeric(15,2)` | NOT NULL | Maximum spend allowed in the period |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | Currency of the limit; incoming items are converted to this |
| `period_type` | `text` | NOT NULL | `monthly` \| `weekly` \| `custom` |
| `period_anchor_day` | `int` | NULLABLE | For `monthly`: day of month the period starts (1–28) |
| `custom_start` | `date` | NULLABLE | For `period_type = 'custom'` |
| `custom_end` | `date` | NULLABLE | For `period_type = 'custom'` |
| `rollover` | `bool` | NOT NULL DEFAULT false | Reserved: carry unspent budget to next period |
| `is_active` | `bool` | NOT NULL DEFAULT true | — |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### `budget_progress`

Running counter of current-period spend per goal. Upserted on each `TransactionCategorized` event.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `goal_id` | `uuid` | NOT NULL FK → `budget_goals.id` | — |
| `user_id` | `uuid` | NOT NULL | Denormalised for fast user-scoped queries |
| `period_start` | `date` | NOT NULL | Current period start date |
| `period_end` | `date` | NOT NULL | Current period end date |
| `current_spend` | `numeric(15,2)` | NOT NULL DEFAULT 0 | Cumulative spend this period in `budget_goals.currency` |
| `updated_at` | `timestamptz` | NULLABLE | — |

**Unique constraint**: `UNIQUE (goal_id, period_start)`. One progress row per goal per period; the handler upserts on this key.

`current_spend` accumulates amounts converted to `budget_goals.currency` via the `fx.convert()` service. Never add raw foreign-currency amounts without conversion.

#### `budget_alerts`

Deduplication log. Prevents duplicate 80% and 100% alerts per goal per period.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `goal_id` | `uuid` | NOT NULL FK → `budget_goals.id` | — |
| `triggered_at` | `timestamptz` | NOT NULL | — |
| `threshold_percent` | `int` | NOT NULL | `80` or `100` |
| `current_spend` | `numeric(15,2)` | NOT NULL | Spend at the time the alert fired |
| `period_start` | `date` | NOT NULL | Which period this alert belongs to |
| `created_at` | `timestamptz` | NOT NULL | — |

**Unique constraint**: `UNIQUE (goal_id, period_start, threshold_percent)`. Before publishing `BudgetLimitWarning` or `BudgetLimitBreached`, handlers check for a matching row here.

---

### peers

#### `peer_contacts`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `name` | `text` | NOT NULL | Display name e.g. "Rahul", "Mom" |
| `phone` | `text` | NULLABLE | Informational only — not used for notifications |
| `notes` | `text` | NULLABLE | Any context the user wants to store |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

#### `peer_balances`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `peer_id` | `uuid` | NOT NULL FK → `peer_contacts.id` | — |
| `description` | `text` | NOT NULL | What this balance is for e.g. "Goa trip accommodation" |
| `original_amount` | `numeric(15,2)` | NOT NULL | Amount at balance creation |
| `settled_amount` | `numeric(15,2)` | NOT NULL DEFAULT 0 | Total settled so far |
| `remaining_amount` | `numeric(15,2)` | GENERATED ALWAYS AS (`original_amount - settled_amount`) STORED | Always consistent with `settled_amount` |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | — |
| `direction` | `text` | NOT NULL | `owed_to_me` \| `i_owe` |
| `status` | `text` | NOT NULL DEFAULT `'open'` | `open` \| `partial` \| `settled` |
| `linked_transaction_id` | `uuid` | NULLABLE | → `transactions.id` (no PG FK); optional link to the originating transaction |
| `notes` | `text` | NULLABLE | — |
| `created_at` | `timestamptz` | NOT NULL | — |
| `updated_at` | `timestamptz` | NULLABLE | — |

`remaining_amount` is a PostgreSQL generated column — the application reads it directly and never recomputes it.

**Status transitions**: `open` → `partial` on any settlement that does not fully clear; `partial` → `settled` or `open` → `settled` when `remaining_amount = 0`.

#### `peer_settlements`

Append-only settlement log. Once written, rows are never edited.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `balance_id` | `uuid` | NOT NULL FK → `peer_balances.id` | — |
| `amount` | `numeric(15,2)` | NOT NULL | Amount settled in this entry |
| `currency` | `char(3)` | NOT NULL DEFAULT `'INR'` | — |
| `settled_at` | `timestamptz` | NOT NULL | When the settlement occurred |
| `method` | `text` | NULLABLE | `cash` \| `upi` \| `bank_transfer` \| `other` |
| `linked_transaction_id` | `uuid` | NULLABLE | → `transactions.id` (no PG FK); set if settlement arrived as a bank credit |
| `notes` | `text` | NULLABLE | — |
| `created_at` | `timestamptz` | NOT NULL | — |

Corrections are recorded as new settlement entries, not edits to existing rows.

#### Views

```sql
CREATE VIEW peer_contacts_public AS
SELECT id, user_id, name FROM peer_contacts;
```

Used by: `earnings` — during credit classification, queries this view filtered by `user_id` to check whether a credit description mentions a known peer's name (indicating a repayment rather than income).

---

### notifications

#### `notifications`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `type` | `text` | NOT NULL | Source event type e.g. `budgets.BudgetLimitWarning` |
| `title` | `text` | NOT NULL | Short heading e.g. "Budget limit reached" |
| `body` | `text` | NOT NULL | Detail message shown to the user |
| `route` | `text` | NOT NULL | Frontend navigation target e.g. `/budgets` |
| `primary_entity_id` | `uuid` | NULLABLE | Main entity the notification relates to (goal_id, transaction_id, job_id, account_id) |
| `secondary_entity_id` | `uuid` | NULLABLE | Second entity when two are needed (e.g. sip_id alongside transaction_id for `SIPDetected`) |
| `period_start` | `date` | NULLABLE | Budget period start; used as part of the idempotency key for budget notifications |
| `read_at` | `timestamptz` | NULLABLE | NULL = unread; set on user action |
| `created_at` | `timestamptz` | NOT NULL | — |

**Idempotency guard** per notification type (checked before inserting):

| Notification type | Key columns |
|---|---|
| `BudgetLimitWarning`, `BudgetLimitBreached` | `type + primary_entity_id (goal_id) + period_start` |
| `SIPDetected` | `type + primary_entity_id (transaction_id) + secondary_entity_id (sip_id)` |
| `EarningClassificationNeeded` | `type + primary_entity_id (transaction_id)` |
| `ExtractionCompleted`, `ExtractionPartiallyCompleted` | `type + primary_entity_id (job_id)` |
| `AccountLinked` | `type + primary_entity_id (account_id)` |
| `ImportCompleted` | `type + primary_entity_id (job_id)` |

No outbox table — notifications only consume events and write to their own table.

---

### fx

#### `fx_rates`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `from_currency` | `char(3)` | NOT NULL | ISO 4217 code e.g. `USD` |
| `to_currency` | `char(3)` | NOT NULL | ISO 4217 code e.g. `INR` |
| `rate` | `numeric(18,6)` | NOT NULL | 1 unit of `from_currency` = `rate` units of `to_currency` |
| `fetched_at` | `timestamptz` | NOT NULL | When this rate was fetched |
| `created_at` | `timestamptz` | NOT NULL | — |

**Unique constraint**: `UNIQUE (from_currency, to_currency)`. One current rate per pair; upserted on each refresh. INR is the base: all rates are stored as X→INR. Non-INR pairs are triangulated through INR at query time.

No outbox table — the fx domain does not publish domain events.

---

### import_

#### `import_jobs`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `user_id` | `uuid` | NOT NULL | — |
| `file_path` | `text` | NOT NULL | User-scoped storage path |
| `original_filename` | `text` | NULLABLE | For display |
| `source_type` | `text` | NOT NULL | `csv_generic` \| `xlsx_generic` \| `splitwise_csv` |
| `temporal_workflow_id` | `text` | NULLABLE | For sending `ColumnMappingConfirmed` signal |
| `status` | `text` | NOT NULL DEFAULT `'uploaded'` | `uploaded` \| `awaiting_mapping` \| `processing` \| `completed` \| `failed` |
| `total_rows` | `int` | NULLABLE | Set after file is parsed |
| `imported_rows` | `int` | NOT NULL DEFAULT 0 | Rows submitted to `ImportBatchReady` |
| `skipped_rows` | `int` | NOT NULL DEFAULT 0 | Rows skipped due to duplicate fingerprints |
| `failed_rows` | `int` | NOT NULL DEFAULT 0 | Rows that could not be parsed |
| `created_at` | `timestamptz` | NOT NULL | — |
| `completed_at` | `timestamptz` | NULLABLE | — |

#### `import_column_mappings`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `job_id` | `uuid` | NOT NULL FK → `import_jobs.id` | — |
| `source_column` | `text` | NOT NULL | Column name as it appears in the uploaded file |
| `mapped_to` | `text` | NOT NULL | `date` \| `description` \| `debit_amount` \| `credit_amount` \| `amount` \| `balance` \| `category` \| `ignore` |
| `created_at` | `timestamptz` | NOT NULL | — |

#### `import_row_errors`

Normalised replacement for the former `import_jobs.error_log jsonb` column. Stores one row per failed or unparseable row in the import file.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `uuid` | PK | — |
| `job_id` | `uuid` | NOT NULL FK → `import_jobs.id` | — |
| `row_index` | `int` | NOT NULL | 0-based index of the row in the uploaded file |
| `reason` | `text` | NOT NULL | Human-readable parse or validation failure reason |
| `created_at` | `timestamptz` | NOT NULL | — |

---

## Cross-Domain References

No PostgreSQL foreign key constraints cross domain boundaries. Referential integrity is enforced at the application layer. This preserves domain isolation — no domain's schema has a compile-time dependency on another domain's schema.

| Column (from → to) | Kind | Notes |
|---|---|---|
| `transactions.account_id` → `bank_accounts.id` or `credit_cards.id` | Cross-domain, no PG FK | `account_kind` disambiguates which table |
| `transaction_items.category_id` → `categories.id` | Cross-domain, no PG FK | Service validates category exists for this user |
| `transaction_items.transaction_id` → `transactions.id` | Within-domain PG FK | — |
| `raw_extracted_rows.job_id` → `extraction_jobs.id` | Within-domain PG FK | — |
| `raw_extracted_rows.final_category_id` → `categories.id` | Cross-domain, no PG FK | — |
| `raw_extracted_rows.transaction_id` → `transactions.id` | Cross-domain, no PG FK | Set after row is committed |
| `raw_row_items.row_id` → `raw_extracted_rows.id` | Within-domain PG FK | — |
| `extraction_jobs.upload_id` → `statement_uploads.id` | Within-domain PG FK | — |
| `earnings.transaction_id` → `transactions.id` | Cross-domain, no PG FK | Nullable — manually entered earnings have no transaction |
| `earnings.source_id` → `earning_sources.id` | Within-domain, no PG FK | Nullable — earnings without a named source |
| `holdings.instrument_id` → `instruments.id` | Within-domain PG FK | — |
| `sip_registrations.instrument_id` → `instruments.id` | Within-domain PG FK | — |
| `sip_registrations.bank_account_id` → `bank_accounts.id` | Cross-domain, no PG FK | Deactivated when account is removed |
| `valuation_snapshots.holding_id` → `holdings.id` | Within-domain PG FK | — |
| `fd_details.holding_id` → `holdings.id` | Within-domain PG FK | UNIQUE — one FD detail per holding |
| `budget_goals.category_id` → `categories.id` | Cross-domain, no PG FK | — |
| `budget_progress.goal_id` → `budget_goals.id` | Within-domain PG FK | — |
| `budget_alerts.goal_id` → `budget_goals.id` | Within-domain PG FK | — |
| `peer_balances.peer_id` → `peer_contacts.id` | Within-domain PG FK | — |
| `peer_balances.linked_transaction_id` → `transactions.id` | Cross-domain, no PG FK | Optional link to originating transaction |
| `peer_settlements.balance_id` → `peer_balances.id` | Within-domain PG FK | — |
| `peer_settlements.linked_transaction_id` → `transactions.id` | Cross-domain, no PG FK | Optional link to a bank credit for the settlement |
| `import_column_mappings.job_id` → `import_jobs.id` | Within-domain PG FK | — |
| `import_row_errors.job_id` → `import_jobs.id` | Within-domain PG FK | — |
| `categorization_rules.category_id` → `categories.id` | Within-domain, no PG FK | User-created rules reference user or default categories |
| `categories.parent_id` → `categories.id` | Self-referential, no PG FK | Reserved for sub-categories (future) |

---

## SQL Views — Summary

| View | Owning domain | Consumers | Columns exposed |
|---|---|---|---|
| `users_public` | `identity` | Any domain needing to display a user name | `id`, `name` |
| `user_accounts_summary` | `accounts` | `statements`, `transactions` | `id`, `user_id`, `nickname`, `bank_name`, `account_kind`, `subtype`, `last4`, `currency`, `is_active` |
| `categories_for_user` | `categorization` | `statements` (via `suggest_category()`), `import_` | `id`, `name`, `slug`, `kind`, `icon`, `is_default`, `parent_id`, `user_id` |
| `transactions_with_categories` | `transactions` | `earnings`, `budgets` | `id`, `user_id`, `account_id`, `account_kind`, `amount`, `currency`, `date`, `type`, `source`, `raw_description`, `notes`, `item_id`, `category_id`, `item_amount`, `item_currency`, `label`, `is_primary` |
| `peer_contacts_public` | `peers` | `earnings` | `id`, `user_id`, `name` |

Cross-domain reads always go through a view. No domain may query another domain's tables directly.

---

## Key Unique Constraints

| Table | Constraint | Purpose |
|---|---|---|
| `users` | `UNIQUE (phone_e164)` | One account per phone number |
| `sessions` | `UNIQUE (access_token_jti)` | JWT IDs are globally unique |
| `sessions` | `UNIQUE (refresh_token_jti)` | JWT IDs are globally unique |
| `transactions` | `UNIQUE (user_id, fingerprint)` | Deduplication across all import sources |
| `holdings` | `UNIQUE (user_id, instrument_id)` | One holding per instrument per user |
| `valuation_snapshots` | `UNIQUE (holding_id, snapshot_date)` | One snapshot per holding per day (upserted) |
| `fx_rates` | `UNIQUE (from_currency, to_currency)` | One current rate per currency pair (upserted) |
| `budget_progress` | `UNIQUE (goal_id, period_start)` | One progress row per goal per period (upserted) |
| `budget_alerts` | `UNIQUE (goal_id, period_start, threshold_percent)` | Deduplication of 80% and 100% alerts |
| `fd_details` | `UNIQUE (holding_id)` | One FD detail record per holding |

---

## Generated Columns

| Table | Column | Expression |
|---|---|---|
| `peer_balances` | `remaining_amount numeric(15,2) GENERATED ALWAYS AS (original_amount - settled_amount) STORED` | Always consistent with `settled_amount`; application reads it directly and never recomputes it in Python |

---

## Data Integrity Rules

1. **No cross-domain PostgreSQL foreign keys.** Referential integrity for cross-domain references is enforced in the service layer, not the database.

2. **Every row is user-scoped.** All application queries include `WHERE user_id = :user_id`. PostgreSQL RLS enforces this at the database level as a second layer.

3. **Amounts are `numeric(15,2)`.** Never `float`. Floats are unsuitable for financial arithmetic.

4. **Currency stored alongside every amount.** Every `amount` column has a sibling `currency char(3)` column. Never assume INR.

5. **Fingerprints for deduplication.** `transactions.fingerprint` is SHA-256 of `lower(trim(raw_description)) + date.isoformat() + str(amount)`. The unique constraint is `(user_id, fingerprint)` — two users may have identical-looking transactions without fingerprint collision. Manual entries have `fingerprint = NULL` and are exempt.

6. **Transfer transactions are excluded from budgets and earnings.** Any transaction with `type = 'transfer'` is a self-transfer. Budget and earnings handlers must skip these. A transaction may be marked as `transfer` by automatic detection or by the user.

7. **Budget spend is always converted to goal currency.** `budget_progress.current_spend` accumulates amounts converted to `budget_goals.currency` via `fx.convert()` at the time of the `TransactionCategorized` event. Raw foreign-currency amounts must never be added directly.

8. **Peer settlement currency mismatch is a known limitation.** If a settlement is recorded in a different currency than `peer_balances.currency`, the `remaining_amount` generated column does not automatically convert — it subtracts the raw amounts. Users must enter the equivalent amount in the balance currency to correctly reduce `remaining_amount`.

9. **`outbox.payload` is the only justified `jsonb` column.** Event payloads vary across event types and are consumed only by the EventBus, not queried by domain logic. All other structured data uses typed, normalised columns.
