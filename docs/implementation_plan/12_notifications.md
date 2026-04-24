# Implementation Plan: notifications

## Status
**Not started** — `api.py` and `bootstrap.py` are empty stubs.

## Domain References
- Domain spec: [`docs/domains/notifications.md`](../domains/notifications.md)
- Data model: [`docs/data-model.md`](../data-model.md#notifications)
- User slices: 36-view-notifications, 37-mark-notifications-read

## Dependencies
- `identity` — JWT auth middleware
- All event-publishing domains must be registered before notification handlers can fire:
  - `accounts` — publishes `AccountLinked`
  - `statements` — publishes `ExtractionCompleted`, `ExtractionPartiallyCompleted`
  - `earnings` — publishes `EarningClassificationNeeded`
  - `investments` — publishes `SIPDetected`
  - `budgets` — publishes `BudgetLimitWarning`, `BudgetLimitBreached`
  - `import_` — publishes `ImportCompleted`

`notifications` is the last domain to implement — it only consumes, never produces.

## What to Build
Pure event consumer that converts domain events into user-facing in-app notification banners. No business logic of its own beyond message formatting and routing. No outbox — this domain only receives events and writes to its own `notifications` table. Notifications are never deleted, only marked read. Idempotency is enforced per notification type to prevent duplicate banners from at-least-once event delivery.

## Tables to Create
| Table | Key columns |
|---|---|
| `notifications` | `user_id`, `type`, `title`, `body`, `route`, `primary_entity_id` (nullable), `secondary_entity_id` (nullable), `period_start` (nullable), `read_at` (nullable) |

**No outbox table** — `notifications` does not publish events.

`type` stores the source event type string (e.g., `budgets.BudgetLimitWarning`) — used for idempotency lookups and frontend grouping.

## Events Published
None.

## Events Subscribed
| Event | Publisher | Notification created |
|---|---|---|
| `accounts.AccountLinked` | `accounts` | "Account added — upload a statement to start tracking." |
| `statements.ExtractionCompleted` | `statements` | "Statement processed — N transactions ready to review." |
| `statements.ExtractionPartiallyCompleted` | `statements` | "Statement partially imported — rows from X to Y were discarded." |
| `earnings.EarningClassificationNeeded` | `earnings` | "New credit to classify — is this income or a repayment?" |
| `investments.SIPDetected` | `investments` | "SIP payment detected — confirm to link." |
| `budgets.BudgetLimitWarning` | `budgets` | "Approaching budget limit — used {percent}%." |
| `budgets.BudgetLimitBreached` | `budgets` | "Budget limit exceeded." |
| `import_.ImportCompleted` | `import_` | "Import complete — N transactions imported." |

## Idempotency Keys (per notification type)
| Type | Guard condition |
|---|---|
| `BudgetLimitWarning`, `BudgetLimitBreached` | `type + primary_entity_id (goal_id) + period_start` |
| `SIPDetected` | `type + primary_entity_id (transaction_id) + secondary_entity_id (sip_id)` |
| `EarningClassificationNeeded` | `type + primary_entity_id (transaction_id)` |
| `ExtractionCompleted`, `ExtractionPartiallyCompleted` | `type + primary_entity_id (job_id)` |
| `AccountLinked` | `type + primary_entity_id (account_id)` |
| `ImportCompleted` | `type + primary_entity_id (job_id)` |

Before inserting a notification, query for an existing row matching these key columns. If found, skip insertion.

## API Endpoints
| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications` | List notifications for the user (most recent first, paginated) |
| `GET` | `/notifications?unread=true` | List only unread notifications |
| `PATCH` | `/notifications/{id}/read` | Mark a single notification as read |
| `PATCH` | `/notifications/read-all` | Mark all unread notifications as read |

## Action Steps

### Step 1 — Create `models.py`
Define `Notification` model only. No outbox.
- `Notification`: `Base`, `IDMixin`, `TimestampMixin` (immutable — no `updated_at`; `read_at` is the only mutable field, updated separately)
- `type`: String, not null (event type string, not a DB enum — allows new event types without migrations)
- `title`, `body`, `route`: String, not null
- `primary_entity_id`, `secondary_entity_id`: nullable `uuid` (no PG FK — cross-domain references)
- `period_start`: nullable `date` — used as part of budget idempotency key
- `read_at`: nullable `timestamptz`

### Step 2 — Create Alembic migration
`uv run alembic revision --autogenerate -m "notifications: add notifications table"`.
Add indexes for frequent query patterns:
- `idx_notifications_user_id_read_at` on `(user_id, read_at)` — for unread count
- `idx_notifications_user_id_created_at` on `(user_id, created_at DESC)` — for ordered list

### Step 3 — Create `repositories.py`
Key methods:
- `create_notification(user_id, type, title, body, route, primary_entity_id?, secondary_entity_id?, period_start?) -> Notification`
- `notification_exists(user_id, type, primary_entity_id?, secondary_entity_id?, period_start?) -> bool` — idempotency check
- `list_notifications(user_id, unread_only=False, page, page_size) -> Page[Notification]` — ordered by `created_at DESC`
- `get_notification(user_id, notification_id) -> Notification | None`
- `mark_read(notification) -> None` — sets `read_at = now()` if currently NULL
- `mark_all_read(user_id) -> int` — `UPDATE ... SET read_at = now() WHERE user_id = :uid AND read_at IS NULL`; returns count updated

### Step 4 — Create `schemas.py`
- `NotificationResponse` — id, type, title, body, route, primary_entity_id, secondary_entity_id, period_start, read_at, created_at
- No create/update schemas — notifications are only created by event handlers, never via API

### Step 5 — Create `services.py`
- `list_notifications(user_id, unread_only, page, page_size) -> Page[NotificationResponse]`
- `mark_read(user_id, notification_id) -> None`
- `mark_all_read(user_id) -> int` — returns count of notifications marked read
- `_create_notification_if_not_exists(user_id, type, title, body, route, primary_entity_id?, secondary_entity_id?, period_start?) -> None`
  - Check idempotency; insert if not found

Internal notification builder methods (called by event handlers):
- `_on_account_linked(account_id, user_id, nickname, account_kind)` → title: "Account added", body: f"Upload a statement or log a transaction to start tracking {nickname}.", route: `/statements/upload`
- `_on_extraction_completed(job_id, user_id, n, account_name)` → title: "Statement processed", body: f"{n} transactions from your {account_name} statement are ready to review.", route: f`/statements/{job_id}/review`
- `_on_extraction_partially_completed(job_id, user_id, n, discarded_from, discarded_to)` → title: "Statement partially imported", body with date range, route: `/statements/upload`
- `_on_earning_classification_needed(transaction_id, user_id, amount, currency)` → title: "New credit to classify", route: `/earnings/classify`
- `_on_sip_detected(transaction_id, sip_id, user_id, amount, instrument_name)` → title: "SIP payment detected", route: `/investments/sip/confirm`
- `_on_budget_limit_warning(goal_id, user_id, category_id, spent, limit, percent, period_start, period_end)` → title: "Approaching budget limit", route: `/budgets`
- `_on_budget_limit_breached(goal_id, user_id, category_id, spent, limit, period_start)` → title: "Budget limit exceeded", route: `/budgets`
- `_on_import_completed(job_id, user_id, imported_rows, skipped_rows)` → title: "Import complete", route: `/transactions`

### Step 6 — Create `events.py`
All event handlers. Each checks idempotency before inserting.

```python
async def handle_account_linked(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = account_id; idempotency: type + primary_entity_id

async def handle_extraction_completed(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = job_id

async def handle_extraction_partially_completed(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = job_id (different type string from ExtractionCompleted)

async def handle_earning_classification_needed(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = transaction_id

async def handle_sip_detected(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = transaction_id, secondary_entity_id = sip_registration_id

async def handle_budget_limit_warning(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = goal_id, period_start = period_start

async def handle_budget_limit_breached(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = goal_id, period_start = period_start

async def handle_import_completed(payload: dict, session: AsyncSession) -> None:
    # primary_entity_id = job_id
```

### Step 7 — Update `bootstrap.py`
```python
def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.notifications.events import (
        handle_account_linked,
        handle_extraction_completed,
        handle_extraction_partially_completed,
        handle_earning_classification_needed,
        handle_sip_detected,
        handle_budget_limit_warning,
        handle_budget_limit_breached,
        handle_import_completed,
    )
    event_bus.subscribe("accounts.AccountLinked", handle_account_linked)
    event_bus.subscribe("statements.ExtractionCompleted", handle_extraction_completed)
    event_bus.subscribe("statements.ExtractionPartiallyCompleted", handle_extraction_partially_completed)
    event_bus.subscribe("earnings.EarningClassificationNeeded", handle_earning_classification_needed)
    event_bus.subscribe("investments.SIPDetected", handle_sip_detected)
    event_bus.subscribe("budgets.BudgetLimitWarning", handle_budget_limit_warning)
    event_bus.subscribe("budgets.BudgetLimitBreached", handle_budget_limit_breached)
    event_bus.subscribe("import_.ImportCompleted", handle_import_completed)
    # No outbox table — notifications domain does not publish events

def get_temporal_workflows() -> list:
    return []

def get_temporal_activities(*args) -> list:
    return []
```

### Step 8 — Complete `api.py`
4 endpoints. Error mapping:
- `NotificationNotFoundError` → 404

### Step 9 — Register router in `runtime/app.py`
Include `notifications` router under prefix `/notifications`.

## Verification Checklist
- [ ] Replaying `BudgetLimitWarning` twice creates only one notification (idempotency)
- [ ] `SIPDetected` idempotency uses both `primary_entity_id` (transaction_id) AND `secondary_entity_id` (sip_id) — two SIPs on the same transaction generate two separate notifications
- [ ] `GET /notifications?unread=true` returns only notifications where `read_at IS NULL`
- [ ] `PATCH /notifications/read-all` marks all unread notifications for the user and returns count
- [ ] `mark_read` on an already-read notification is a no-op (does not error)
- [ ] All queries filter by `user_id` — no cross-user data leakage
- [ ] No `outbox` table exists in this domain — confirmed by checking bootstrap
- [ ] Ruff + mypy pass with no errors
