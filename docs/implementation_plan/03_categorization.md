# Implementation Plan: categorization

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/categorization.md`](../domains/categorization.md)
- Data model: [`docs/data-model.md`](../data-model.md#categorization)
- User slices: 17-browse-categories, 18-create-custom-category, 19-create-categorization-rule, 20-manage-categorization-rules

## Dependencies
- `identity` — all queries filter by `user_id`.

## What to Build
The category taxonomy (default system categories + user custom categories) and the rules engine (text patterns users define to auto-classify transactions). Exposes the `suggest_category()` service method used synchronously by the `statements` domain during Temporal workflow activities. Provides the `categories_for_user` SQL view consumed by `statements` and `import_`.

This domain must be seeded with default categories on first run — the seed script runs in the Alembic migration or application startup, not via API.

## Tables to Create
| Table | Key columns |
|---|---|
| `categories` | `user_id` (nullable), `name`, `slug`, `kind`, `parent_id`, `icon`, `is_default`, `is_active` |
| `categorization_rules` | `user_id`, `pattern`, `match_type`, `category_id`, `priority`, `is_active` |
| `categorization_outbox` | standard outbox schema |

Note: `categories.user_id` is `NULLABLE` — `NULL` means system default, shared across all users. This is enforced at the application layer.

## SQL View to Create
```sql
CREATE VIEW categories_for_user AS
SELECT id, name, slug, kind, icon, is_default, parent_id, NULL::uuid AS user_id
FROM categories WHERE user_id IS NULL AND is_active = true
UNION ALL
SELECT id, name, slug, kind, icon, is_default, parent_id, user_id
FROM categories WHERE user_id IS NOT NULL AND is_active = true;
```
**Critical**: callers must apply `WHERE user_id = :uid OR user_id IS NULL` to get both defaults and user categories. A plain `WHERE user_id = :uid` silently omits all defaults.

## Default Seed Data
Seed in the Alembic migration (one-time `INSERT ... ON CONFLICT DO NOTHING`):

**Expense categories** (`kind='expense'`, `user_id=NULL`, `is_default=true`):
Food & Dining, Groceries, Transport, Utilities, Shopping, Health & Medical, Entertainment, Travel, Education, Personal Care, Subscriptions, EMI & Loans, Rent, Investments (outflow), Others

**Income categories** (`kind='income'`, `user_id=NULL`, `is_default=true`):
Salary, Freelance, Rental Income, Dividends, Interest, Business Income

**Transfer category** (`kind='transfer'`, `user_id=NULL`, `is_default=true`):
Self Transfer — assigned automatically to transactions with `type='transfer'`. Never shown to users for manual selection.

## Events Published
| Event | Consumed by |
|---|---|
| `categorization.CategoryCreated` | Audit only — no active consumers |

## Events Subscribed
None.

## Service Methods Exposed (cross-domain)
### `suggest_category(description, user_id, amount, transaction_type?) → CategorySuggestion`
This is **Pattern 3 (direct service call)** — the only justified instance. Called synchronously inside the `statements` Temporal workflow activity. Reason: the workflow must know the confidence score before deciding whether to pause for user input.

Resolution order:
1. If `transaction_type == 'transfer'`: return "Self Transfer" category with `confidence=1.0, source='rule'`
2. Check `categorization_rules` for this user (ordered by `priority DESC`) — if a rule matches, return `confidence=1.0, source='rule'`
3. Call the ADK categorisation agent with description, amount, user category list, and recent similar transactions as context
4. Return ADK result (may have `confidence < 0.85` — caller decides whether to pause)

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/categories` | List all categories visible to the user (defaults + custom) |
| `POST` | `/categories` | Create a custom category |
| `PATCH` | `/categories/{id}` | Edit a custom category (name, icon, is_active) — cannot edit default categories |
| `GET` | `/categorization-rules` | List the user's categorization rules |
| `POST` | `/categorization-rules` | Create a new rule |
| `PATCH` | `/categorization-rules/{id}` | Edit a rule (pattern, match_type, priority, is_active) |
| `DELETE` | `/categorization-rules/{id}` | Delete a rule |

## Action Steps

### Step 1 — Create `models.py`
Define `Category`, `CategorizationRule`, and `CategorizationOutbox`.
- `Category`: `user_id` is `Mapped[uuid.UUID | None]` (nullable)
- `kind`: `CheckConstraint` for `expense | income | transfer`
- `match_type` on `CategorizationRule`: `CheckConstraint` for `contains | starts_with | exact | regex`
- Self-referential `parent_id` FK on `Category` (nullable, no cascade — reserved for future subcategories)
- Unique constraint: `(slug, user_id)` on `Category`. For `user_id IS NULL` rows, PostgreSQL treats each NULL as distinct — add a partial unique index `WHERE user_id IS NULL` on `slug` to prevent duplicate default slugs.

### Step 2 — Create Alembic migration for tables + seed data
Single migration file: `uv run alembic revision -m "categorization: add categories, rules, outbox, seed defaults"`.
Include the `INSERT ... ON CONFLICT DO NOTHING` seed data for default categories in `upgrade()`. Include `DELETE FROM categories WHERE is_default = true` in `downgrade()`.

### Step 3 — Create Alembic migration for `categories_for_user` view
Separate migration: `uv run alembic revision -m "categorization: add categories_for_user view"`.

### Step 4 — Create `repositories.py`
Key methods:
- `get_categories_for_user(user_id) -> list[Category]` — queries `categories_for_user` view via raw SQL with `WHERE user_id = :uid OR user_id IS NULL`
- `get_category_by_id(category_id, user_id) -> Category | None` — validates user can see this category
- `get_default_category_by_slug(slug) -> Category | None` — used during seeding and transfer detection
- `create_category(user_id, **fields) -> Category`
- `update_category(category, **fields) -> Category`
- `get_rules_for_user(user_id) -> list[CategorizationRule]` — ordered by `priority DESC`
- `create_rule(user_id, **fields) -> CategorizationRule`
- `update_rule(rule, **fields) -> CategorizationRule`
- `delete_rule(rule) -> None`
- `find_matching_rule(user_id, description) -> CategorizationRule | None` — applies rules in priority order

### Step 5 — Create `schemas.py`
- `CategoryResponse` — id, name, slug, kind, icon, is_default, parent_id, user_id (nullable)
- `CategoryCreate` — name, slug, kind, icon (optional), parent_id (optional)
- `CategoryUpdate` — name, icon, is_active (all optional; cannot change kind or slug)
- `RuleCreate` — pattern, match_type, category_id, priority
- `RuleUpdate` — all fields optional
- `RuleResponse`
- `CategorySuggestion` — category_id (nullable), category_name (nullable), confidence (float), source (`rule | ai | none`), item_suggestions (list[str])

### Step 6 — Create `services.py`
- `list_categories(user_id) -> list[CategoryResponse]`
- `create_category(user_id, data) -> CategoryResponse`
  - Validate slug uniqueness for this user
  - Write `CategoryCreated` to outbox in same transaction
- `update_category(user_id, category_id, data) -> CategoryResponse`
  - Reject edits to `is_default=true` categories with a clear error
- `list_rules(user_id) -> list[RuleResponse]`
- `create_rule(user_id, data) -> RuleResponse`
  - Validate `category_id` is visible to this user (query via view)
  - Validate regex pattern compiles if `match_type='regex'`
- `update_rule(user_id, rule_id, data) -> RuleResponse`
- `delete_rule(user_id, rule_id) -> None`
- `suggest_category(description, user_id, amount, transaction_type?, adk_client) -> CategorySuggestion`
  - Implements the resolution order described above
  - Takes `adk_client` as an injected parameter — never imports it directly

### Step 7 — Create `events.py`
```python
@dataclass
class CategoryCreated:
    event_type: ClassVar[str] = "categorization.CategoryCreated"
    category_id: UUID
    user_id: UUID
    name: str
    kind: str
```
No event handlers — this domain does not subscribe to any events.

### Step 8 — Complete `api.py`
7 endpoints. Error mappings:
- `CategoryNotFoundError` → 404
- `CannotEditDefaultCategoryError` → 403
- `DuplicateSlugError` → 409
- `InvalidRegexPatternError` → 422

### Step 9 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    event_bus.register_outbox_table("categorization_outbox")

def get_temporal_workflows() -> list:
    return []

def get_temporal_activities(*args) -> list:
    return []
```

### Step 10 — Register router in `runtime/app.py`
Include the `categorization` router under prefix `/categories` and `/categorization-rules`.

### Step 11 — Verify seed data at startup
In `runtime/lifespan.py`, after DB connection is established, call a `seed_default_categories()` utility that does `INSERT ... ON CONFLICT DO NOTHING` for all default categories. This is idempotent and safe to run on every startup.

## Verification Checklist
- [ ] `GET /categories` returns both default (system) categories and user-created categories
- [ ] A new user with no custom categories sees all 22 default categories
- [ ] Creating a category with `kind='transfer'` is blocked or flagged (only system can create transfer categories)
- [ ] `suggest_category()` runs rules before calling ADK; rule match returns `confidence=1.0`
- [ ] `categories_for_user` view is queryable and the critical filter is documented in the repo method
- [ ] `CategoryCreated` is written to outbox in the same transaction as the category row
- [ ] Ruff + mypy pass with no errors
