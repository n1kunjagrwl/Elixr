# Project Structure

This document describes the codebase layout, the layer import rules, and the conventions every domain package must follow.

---

## Directory Tree

```
elixir/
├── docs/                              ← architecture documentation (this folder)
│   ├── architecture.md
│   ├── data-model.md
│   ├── integrations.md
│   ├── project-structure.md
│   ├── domains/
│   ├── workflows/
│   └── adr/
│
├── src/
│   └── elixir/
│       ├── runtime/                   ← how the app runs
│       │   ├── __init__.py
│       │   ├── app.py                 ← FastAPI factory + domain router registration
│       │   ├── lifespan.py            ← startup/shutdown (DB pool, Temporal, outbox worker)
│       │   └── middleware.py          ← auth, CORS, request logging
│       │
│       ├── platform/                  ← external system adapters
│       │   ├── __init__.py
│       │   ├── db.py                  ← SQLAlchemy async engine + session factory
│       │   ├── temporal.py            ← Temporal client + worker factory
│       │   ├── storage.py             ← file storage interface (local now, S3-ready)
│       │   └── clients/
│       │       ├── __init__.py
│       │       ├── twilio.py
│       │       ├── amfi.py
│       │       ├── coingecko.py
│       │       ├── twelve_data.py
│       │       ├── eodhd.py
│       │       ├── metals_api.py
│       │       └── exchangerate.py
│       │
│       ├── shared/                    ← infrastructure all domains may import
│       │   ├── __init__.py
│       │   ├── config.py              ← pydantic-settings Settings class
│       │   ├── security.py            ← JWT encode/decode, bcrypt, AES-256
│       │   ├── events.py              ← EventBus class + event base dataclass
│       │   ├── outbox.py              ← outbox poller background task
│       │   ├── base.py                ← SQLAlchemy DeclarativeBase + id/timestamps mixin
│       │   ├── exceptions.py          ← ElixirError base + common HTTP errors
│       │   └── pagination.py          ← PagedResponse Pydantic schema
│       │
│       └── domains/
│           ├── identity/
│           │   ├── __init__.py
│           │   ├── models.py          ← SQLAlchemy ORM models
│           │   ├── schemas.py         ← Pydantic request/response schemas
│           │   ├── services.py        ← business logic
│           │   ├── repositories.py    ← DB queries (takes AsyncSession, returns models)
│           │   ├── api.py             ← FastAPI APIRouter
│           │   ├── events.py          ← event dataclasses + handler registrations
│           │   └── workflows/
│           │       ├── __init__.py
│           │       ├── otp_delivery.py   ← @workflow.defn class
│           │       └── activities.py     ← @activity.defn functions
│           │
│           ├── accounts/              ← same structure as identity/
│           ├── statements/
│           ├── transactions/
│           ├── categorization/
│           ├── earnings/
│           ├── investments/
│           ├── budgets/
│           ├── peers/
│           ├── notifications/
│           ├── fx/
│           └── import_/
│
├── tests/
│   ├── unit/                          ← fast, no DB, no network
│   │   └── domains/                   ← mirrors src/elixir/domains/
│   ├── integration/                   ← requires a test DB
│   │   └── domains/
│   └── conftest.py
│
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── {timestamp}_{domain}_{description}.py
│
├── pyproject.toml
├── main.py                            ← entry point: creates app, runs uvicorn
└── .python-version
```

---

## Layer Import Rules

This table defines what each layer is allowed to import. Violations break domain isolation and are treated as bugs.

| Layer | May import from | Must NOT import from |
|---|---|---|
| `runtime/` | `platform/`, `shared/`, `domains/` | — |
| `platform/` | `shared/config` only | `runtime/`, `domains/`, other `platform/` modules |
| `shared/` | `platform/db`, `platform/temporal` | `runtime/`, `domains/` |
| `domains/{x}/` | `shared/`, injected `platform/clients/` | `runtime/`, `domains/{y}/` internals |

**Critical rule**: Domains never import from `runtime/`. A domain's services, repositories, and workflows must be fully executable without a running FastAPI app. This enables isolated unit testing and makes future microservice extraction straightforward.

**Why `platform/clients/` are injected, not imported directly**: External API clients are infrastructure adapters. Receiving them via FastAPI's dependency injection means a domain's service layer can be tested with a mock client without patching imports. It also means swapping a price provider (e.g., Eodhd → Zerodha Kite) only touches `platform/clients/` and the DI wiring in `runtime/app.py`.

---

## Domain Package Conventions

Every domain package has the same internal structure. Each file has a single, clearly defined responsibility.

### `models.py` — ORM table definitions

- Contains SQLAlchemy `Table` definitions or mapped `Model` classes
- No business logic — only column definitions, indexes, and within-domain FK constraints
- Imports from `shared/base.py` for the `DeclarativeBase` and common column mixins
- Cross-domain references are plain `Column(UUID)` with no `ForeignKey()` — just a type hint in the comment

```python
# Good
class Transaction(Base):
    __tablename__ = "transactions"
    id = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id = mapped_column(UUID, nullable=False)          # → identity.users.id (no FK)
    account_id = mapped_column(UUID, nullable=False)        # → accounts.bank_accounts.id or credit_cards.id (no FK)
    amount = mapped_column(Numeric(15, 2), nullable=False)
    ...
```

### `repositories.py` — DB queries

- Accepts an `AsyncSession` as its first argument
- Returns domain model instances or plain Python primitives (never raw SQLAlchemy result rows to callers)
- Contains no business logic — only `SELECT`, `INSERT`, `UPDATE`, `DELETE`
- Cross-domain reads use the SQL view name directly: `text("SELECT * FROM categories_for_user WHERE user_id = :uid")`

### `services.py` — business logic

- Orchestrates repositories and writes outbox events
- No HTTP concerns — no `Request`, no `Response`, no status codes
- Calls repositories to read/write, then writes to the outbox table in the same `AsyncSession` transaction
- Receives external clients via constructor arguments (not via import)

```python
# Good — client injected, not imported
class CategorizationService:
    def __init__(self, session: AsyncSession, adk_client: ADKClient):
        self.repo = CategoryRepository(session)
        self.adk = adk_client
```

### `schemas.py` — API request/response shapes

- Pydantic models only — no SQLAlchemy
- Separate `Request` and `Response` schemas; never expose ORM models directly via API
- Inherits from `shared/pagination.py` for paginated list responses

### `api.py` — FastAPI router

- One `APIRouter` per domain, mounted in `runtime/app.py`
- Calls services only — no direct repository calls, no raw SQL
- Handles HTTP concerns: status codes, response models, error mapping
- Dependency-injects the service and any platform clients it needs

### `events.py` — domain events

- Defines event dataclasses (`@dataclass` with `event_type: ClassVar[str]`)
- Registers handler functions on the shared `EventBus` at module import time
- Handlers receive the deserialized event payload and an `AsyncSession`
- All handlers must be idempotent (the same event may arrive more than once)

```python
@dataclass
class TransactionCreated:
    event_type: ClassVar[str] = "transactions.TransactionCreated"
    transaction_id: UUID
    user_id: UUID
    type: str  # 'debit' | 'credit'
    amount: Decimal
    currency: str
```

### `workflows/` — Temporal workflows and activities

- `workflows/{name}.py` — one file per Temporal workflow (`@workflow.defn`)
- `workflows/activities.py` — all `@activity.defn` functions for this domain
- Activities call services (never repositories directly) — they go through the full business logic layer
- Workflows are pure orchestration: sequence of `await workflow.execute_activity(...)` calls, `await workflow.wait_condition(...)`, signal handlers

---

## Migration Conventions

Alembic migrations live in `alembic/versions/`. Naming convention:

```
{timestamp}_{domain}_{short_description}.py
# e.g.
20260418_120000_identity_create_users_and_sessions.py
20260418_130000_transactions_add_fingerprint_column.py
```

Each migration includes only tables owned by one domain. If a change touches two domains' tables, create two separate migration files with the same timestamp prefix — they can be applied together but are semantically separate.

---

## Test Structure

```
tests/unit/domains/{domain}/
    test_services.py    ← mock repositories, test business logic in isolation
    test_repositories.py ← optional, test complex queries

tests/integration/domains/{domain}/
    test_api.py         ← real DB, test full HTTP flow
```

Unit tests use no DB and no external network. Integration tests use a dedicated test database (same PostgreSQL, different schema) and real Alembic migrations applied fresh per test session. External API calls are always mocked even in integration tests — they are tested via the client unit tests in `tests/unit/platform/clients/`.
