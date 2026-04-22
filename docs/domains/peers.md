# Domain: peers

## Responsibility

Tracks money the user is owed by peers (friends, family, colleagues) and money the user owes to others — arising from shared expenses, split bills, or informal loans. This is a pure manual ledger: the user logs balances themselves and records settlements as they happen. The domain maintains a running `remaining_amount` after each partial settlement and updates the balance status accordingly.

This domain has no event-driven behaviour and no external integrations. It is deliberately simple.

---

## Tables Owned

### `peer_contacts`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `name` | `text` NOT NULL | Display name e.g. "Rahul", "Mom" |
| `phone` | `text` NULLABLE | Phone number (informational only, not used for notifications) |
| `notes` | `text` NULLABLE | Any context the user wants to store |
| `created_at` | `timestamptz` | — |

### `peer_balances`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `peer_id` | `uuid` FK → `peer_contacts.id` | — |
| `description` | `text` NOT NULL | What this balance is for e.g. "Goa trip accommodation" |
| `original_amount` | `numeric(15,2)` NOT NULL | Amount when the balance was created |
| `settled_amount` | `numeric(15,2)` NOT NULL DEFAULT 0 | Total settled so far |
| `remaining_amount` | `numeric(15,2)` GENERATED ALWAYS AS (`original_amount - settled_amount`) STORED | — |
| `currency` | `char(3)` NOT NULL DEFAULT `'INR'` | — |
| `direction` | `text` NOT NULL | `owed_to_me` (peer owes user) \| `i_owe` (user owes peer) |
| `status` | `text` NOT NULL DEFAULT `'open'` | `open` \| `partial` \| `settled` |
| `linked_transaction_id` | `uuid` NULLABLE | → `transactions.id` (no PG FK). Optional link to the originating transaction |
| `created_at` | `timestamptz` | — |
| `notes` | `text` NULLABLE | — |

`status` transitions:
- `open` → `partial`: after any settlement that does not fully clear the balance
- `partial` → `settled`: when `remaining_amount = 0`
- `open` → `settled`: when the first settlement clears the full amount

### `peer_settlements`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `balance_id` | `uuid` FK → `peer_balances.id` | — |
| `amount` | `numeric(15,2)` NOT NULL | Amount settled in this transaction |
| `currency` | `char(3)` NOT NULL DEFAULT `'INR'` | — |
| `settled_at` | `timestamptz` NOT NULL | When the settlement occurred |
| `method` | `text` NULLABLE | `cash` \| `upi` \| `bank_transfer` \| `other` (informational) |
| `linked_transaction_id` | `uuid` NULLABLE | → `transactions.id` (no PG FK). If settlement came in as a bank credit |
| `notes` | `text` NULLABLE | — |

---

## SQL Views Exposed

### `peer_contacts_public`
```sql
CREATE VIEW peer_contacts_public AS
SELECT id, user_id, name FROM peer_contacts;
```

Used by the `earnings` domain during credit classification — it queries this view (filtered by `user_id`) to check whether a credit transaction's description mentions a known peer's name, indicating the credit may be a repayment rather than income. This is Pattern 1 (SQL view), the preferred cross-domain read mechanism.

---

## Events Published

None. The peers domain is purely CRUD — no other domain reacts to peer balance changes.

---

## Events Subscribed

None.

---

## Service Methods Exposed

None. The `earnings` domain reads peer contact names via the `peer_contacts_public` SQL view (Pattern 1) — see SQL Views Exposed above.

---

## Key Design Decisions

**`remaining_amount` as a PostgreSQL generated column.** This ensures `remaining_amount` is always mathematically consistent with `settled_amount` — there is no code path that can accidentally leave them out of sync. The application reads `remaining_amount` directly; it never recomputes it in Python.

**Settlements are an append-only log.** Once a settlement is recorded, it is never edited. If the user made a mistake (logged the wrong amount), they add a correcting settlement entry rather than editing the existing one. This gives an accurate audit trail and avoids ambiguity about what actually happened.

**`linked_transaction_id` optional on both tables.** A user may log a balance that has no corresponding bank transaction (e.g., they paid cash). The link to a transaction is optional and informational — it helps the user reconcile their ledger but is not required. Similarly, a settlement might be a cash handover with no bank record.

**No automatic settlement detection.** The system does not automatically mark a balance as settled when a credit transaction arrives from a known peer. Auto-detection of peer repayments is a hard problem (the description may not match the peer's name) and the consequences of getting it wrong (marking income as a peer repayment) are significant. The user settles balances explicitly.
