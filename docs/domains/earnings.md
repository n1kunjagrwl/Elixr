# Domain: earnings

## Responsibility

Tracks all income the user receives. Earnings can come from two sources: auto-detected credit transactions in a bank statement, or manually entered income records. When the `transactions` domain creates a credit transaction, the earnings domain inspects it and decides whether it looks like income. If it does, it creates an `earnings` record and links it. If it is ambiguous (could be a peer repayment rather than income), it asks the user via a notification.

Peer repayments received from friends or family are explicitly **not** earnings. The system errs toward asking rather than auto-classifying credits as income.

---

## Tables Owned

### `earning_sources`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `name` | `text` NOT NULL | e.g. "Think41 Salary", "Freelance — Acme Corp" |
| `type` | `text` NOT NULL | `salary` \| `freelance` \| `rental` \| `dividend` \| `interest` \| `business` \| `other` |
| `is_active` | `bool` DEFAULT true | Inactive sources are hidden from manual entry dropdowns |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

Earning sources are optional user-defined labels for recurring income origins. A user may have "Think41 Salary" and "Freelance — Acme Corp" as separate sources, allowing income to be analysed by origin.

### `earnings`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | — |
| `transaction_id` | `uuid` NULLABLE | → `transactions.id` (no PG FK). NULL for manually-entered earnings |
| `source_id` | `uuid` NULLABLE | → `earning_sources.id`. NULL if source is not categorised |
| `source_type` | `text` NOT NULL | `salary` \| `freelance` \| `rental` \| `dividend` \| `interest` \| `business` \| `other` |
| `source_label` | `text` | Free-text label, used when `source_id` is NULL |
| `amount` | `numeric(15,2)` NOT NULL | — |
| `currency` | `char(3)` NOT NULL DEFAULT `'INR'` | — |
| `date` | `date` NOT NULL | — |
| `notes` | `text` | — |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

### `outbox`
Standard outbox table.

---

## SQL Views Exposed

None. Earnings data is not currently consumed by other domains in a cross-domain query pattern.

---

## Events Published

### `EarningRecorded`
```python
@dataclass
class EarningRecorded:
    event_type = "earnings.EarningRecorded"
    earning_id: UUID
    user_id: UUID
    source_type: str
    amount: Decimal
    currency: str
    date: date
```

### `EarningClassificationNeeded`
```python
@dataclass
class EarningClassificationNeeded:
    event_type = "earnings.EarningClassificationNeeded"
    transaction_id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    description: str
    # The user needs to classify this credit as: income (which type?) | peer_repayment | ignore
```
Consumed by: `notifications` (creates in-app banner asking the user to classify the credit)

---

## Events Subscribed

### `TransactionCreated` (from `transactions`)

Handler logic when a credit transaction is created:

```
1. If transaction.type == 'transfer': skip entirely. Self-transfers are never income.
   If transaction.type != 'credit': skip.

2. Apply heuristics to estimate whether this is income or a peer repayment:
   a. Check if amount matches a known earning_source pattern
      (e.g., same amount ±5% as a recurring salary credit on a similar day of month)
   b. Check if the description contains keywords like 'SALARY', 'NEFT', 'IMPS', 'salary',
      known employer name patterns
   c. Check against peer_contacts: query the `peer_contacts_public` view (exposed by the
      `peers` domain — Pattern 1 SQL view) to get peer names for this user.
      Does the description mention a known peer's name?

3. If high confidence it's income (score >= 0.85):
   → Create earnings record, publish EarningRecorded
   → Link earnings.transaction_id = transaction.id

4. If high confidence it's a peer repayment (score >= 0.85):
   → Skip — the peers domain handles this

5. If ambiguous:
   → Publish EarningClassificationNeeded
   → User sees in-app notification asking them to classify
   → User submits classification via POST /earnings/classify/{transaction_id}
```

Handler must be idempotent: check if an `earnings` record already exists for this `transaction_id` before creating one.

---

## Service Methods Exposed

None.

---

## Key Design Decisions

**Peer repayments are never auto-classified as income.** A ₹1,500 NEFT from a friend paying back their share of dinner looks identical to a small freelance payment at the DB level. Auto-classifying it as income would inflate the user's income figures. When in doubt, ask — never assume.

**Heuristics before user prompt.** Checking for salary patterns (same amount, same time of month, keyword in description) catches the obvious 80% of credits automatically. The user only sees a classification prompt for genuinely ambiguous credits, reducing notification fatigue.

**`transaction_id` nullable on `earnings`.** Users can manually enter income that doesn't correspond to a bank transaction — cash earnings, foreign transfers not yet in a statement, etc. A manual earning record has `transaction_id = NULL`.

**`source_type` duplicates information from `earning_sources`**. This is intentional — `source_type` allows aggregation by income type (e.g., "total freelance income this year") even for records where `source_id` is NULL or where the source has been deleted.
