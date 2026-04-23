# Domain: categorization

## Responsibility

Owns the category taxonomy and the rules that map transaction descriptions to categories. This domain defines both the default categories that ship with Elixir (seeded on first run) and the user-created custom categories. It also owns the rules engine — patterns a user can define (e.g., "any transaction containing 'Swiggy' → Food & Dining") that are applied automatically before the AI agent is consulted.

The `suggest_category()` service method is the bridge between raw transaction descriptions and the ADK agent during statement processing. It is the only case of Pattern 3 (direct service call) in the architecture — called synchronously inside the Temporal workflow activity because a classification suggestion is needed before the workflow can decide whether to pause for user input.

---

## Tables Owned

### `categories`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NULLABLE | NULL for default categories; set for user-created categories |
| `name` | `text` NOT NULL | Display name e.g. "Food & Dining" |
| `slug` | `text` NOT NULL | URL-safe identifier e.g. `food-dining` |
| `kind` | `text` NOT NULL | `expense` \| `income` \| `transfer` — drives which transactions it applies to |
| `parent_id` | `uuid` NULLABLE FK → `categories.id` | Reserved for sub-categories (future use) |
| `icon` | `text` | Emoji or icon identifier for UI |
| `is_default` | `bool` DEFAULT false | True for system-seeded categories |
| `is_active` | `bool` DEFAULT true | Users can hide categories they never use |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

**Default expense categories** (seeded with `user_id = NULL`, `kind = 'expense'`):
Food & Dining, Groceries, Transport, Utilities, Shopping, Health & Medical, Entertainment, Travel, Education, Personal Care, Subscriptions, EMI & Loans, Rent, Investments (outflow), Others

**Default income categories** (`kind = 'income'`):
Salary, Freelance, Rental Income, Dividends, Interest, Business Income

**Default transfer category** (`kind = 'transfer'`):
Self Transfer — assigned automatically to transactions with `type = 'transfer'`. Excluded from all budget and earnings calculations.

### `categorization_rules`
| Column | Type | Description |
|---|---|---|
| `id` | `uuid` PK | — |
| `user_id` | `uuid` NOT NULL | Rules are always user-specific |
| `pattern` | `text` NOT NULL | The text to match against `raw_description` |
| `match_type` | `text` NOT NULL | `contains` \| `starts_with` \| `exact` \| `regex` |
| `category_id` | `uuid` NOT NULL | → `categories.id` (no PG FK) |
| `priority` | `int` DEFAULT 0 | Higher priority rules are checked first |
| `is_active` | `bool` DEFAULT true | — |
| `created_at` | `timestamptz` | — |
| `updated_at` | `timestamptz` | — |

### `outbox`
Standard outbox table.

---

## SQL Views Exposed

### `categories_for_user`
```sql
CREATE VIEW categories_for_user AS
SELECT
    c.id,
    c.name,
    c.slug,
    c.kind,
    c.icon,
    c.is_default,
    c.parent_id,
    NULL::uuid AS user_id   -- defaults have no user_id
FROM categories c
WHERE c.user_id IS NULL AND c.is_active = true

UNION ALL

SELECT
    c.id,
    c.name,
    c.slug,
    c.kind,
    c.icon,
    c.is_default,
    c.parent_id,
    c.user_id
FROM categories c
WHERE c.user_id IS NOT NULL AND c.is_active = true;
```

**Critical filter rule**: Default categories have `user_id = NULL`. Callers must use `WHERE user_id = :uid OR user_id IS NULL` to get both the user's custom categories and the system defaults. A plain `WHERE user_id = :uid` will silently return only custom categories and miss all defaults — producing empty category lists for new users.

---

## Events Published

### `CategoryCreated`
```python
@dataclass
class CategoryCreated:
    event_type = "categorization.CategoryCreated"
    category_id: UUID
    user_id: UUID
    name: str
    kind: str
```

---

## Events Subscribed

None.

---

## Service Methods Exposed

### `suggest_category(description, user_id, amount, context) → CategorySuggestion`

This is a Pattern 3 direct service call, used by the `statements` domain's Temporal activity.

```python
@dataclass
class CategorySuggestion:
    category_id: UUID | None
    category_name: str | None
    confidence: float     # 0.0–1.0
    source: str           # 'rule' | 'ai' | 'none'
    item_suggestions: list[str]  # optional item labels suggested by AI
```

**Resolution order:**
0. If the caller provides `transaction_type = 'transfer'`: return the "Self Transfer" category with `confidence=1.0, source='rule'` immediately. Transfer detection takes precedence over all other rules.
1. Check `categorization_rules` for this user — if a rule matches (by priority), return `confidence=1.0, source='rule'`
2. If no rule matches, call the ADK categorisation agent with the description, amount, user's category list (queried with `WHERE user_id = :uid OR user_id IS NULL`), and recent similar transactions as context
3. ADK agent returns a suggested category and confidence score
4. If ADK returns `confidence < 0.85`, return `source='ai'` with the low confidence — caller decides whether to pause for user input

**Why synchronous**: The workflow must know the confidence score before it can decide whether to pause. Making this async would require additional state management in Temporal with no benefit.

---

## Key Design Decisions

**`user_id = NULL` for default categories.** Rather than copying default categories into every user's account on registration, they live once with `user_id = NULL` and are merged via the `categories_for_user` view. Users only write new rows when they create custom categories. This avoids 15 rows per user at registration time and makes updating a default category's icon or name a single-row change.

**`kind` field separates expense, income, and transfer categories.** Valid values: `expense` | `income` | `transfer`. The UI for categorising a debit shows only expense categories; credits show only income categories; transactions with `type = 'transfer'` are assigned to transfer categories and excluded from budget and earnings tracking. A default "Self Transfer" category with `kind = 'transfer'` is seeded at startup. Keeping `kind` as a column rather than inferred from category name makes filtering trivial.

**Rules engine runs before AI.** User-defined rules are deterministic and free (no API cost). Running them first means known merchants are classified instantly without an ADK call, saving latency and cost for the 80% of transactions the user has already trained the system on.

**`regex` match type in rules.** Supports power users who want patterns like `^UPI/\d+/ZOMATO` to precisely match UPI reference numbers. The UI should warn users when they enter a regex with a validation step.
