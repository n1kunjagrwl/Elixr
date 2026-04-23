# Elixir — Claude Code Instructions

## What This Project Is

Elixir is a multi-user personal finance PWA for Indian users. It tracks expenses, income, investments, and peer balances. Users upload bank/credit card statements or log transactions manually; a Google ADK AI agent categorises transactions and asks for clarification when uncertain.

**It is not**: a bank connection tool, a balance reconciler, or a tax calculator. No live bank APIs. No joint accounts.

---

## Confirm Before Implementing

> **Never assume. Never build speculatively.**

If something is not documented in `docs/` or an ADR in `docs/adr/`, do not write code for it. If a question arises mid-implementation ("should this live in `shared/` or `platform/`?"), stop and ask — do not guess. This applies to feature scope, file placement, library choices, domain design, and API contract decisions.

---

## Codebase Map

```
src/elixir/
├── runtime/        # FastAPI app factory, middleware, DI composition root, config
├── platform/       # Infrastructure adapters: DB, Temporal, security, file storage, API clients
├── shared/         # Domain-safe utilities: EventBus, outbox poller, base models, exceptions
└── domains/        # 12 domain packages (identity, accounts, statements, transactions,
                    #   categorization, earnings, investments, budgets, peers,
                    #   notifications, fx, import_)

docs/
├── architecture.md          # System overview, tech stack, inter-domain patterns — READ FIRST
├── data-model.md            # Tables, cross-domain references, ownership rules
├── integrations.md          # External APIs: purpose, rate limits, owning domain
├── project-structure.md     # Full directory tree, layer import rules, conventions
├── domains/                 # One file per domain: tables, events, views, key decisions
├── workflows/               # Step-by-step Temporal workflow descriptions
├── slices/                  # 37 user journey slices — business operations end-to-end
└── adr/                     # Architecture Decision Records — the WHY behind every decision
```

---

## Layer Import Rules (hard rules — violations are bugs)

| Layer | May import | Must NOT import |
|---|---|---|
| `runtime/` | `platform/`, `shared/`, `domains/` | — |
| `platform/` | stdlib + third-party only | `runtime/`, `shared/`, `domains/` |
| `shared/` | stdlib + third-party only | `runtime/`, `platform/`, `domains/` |
| `domains/{x}/` | `shared/`, injected `platform/clients/` | `runtime/`, `platform/` directly, other `domains/{y}/` internals |

- `Settings` is only instantiated in `runtime/config.py`. No domain, platform, or shared module may import it.
- External API clients are injected via FastAPI DI — never imported directly inside a domain.
- Domains never import from `runtime/` — services must be testable without a running HTTP server.

---

## Domain Package Conventions

Every domain has the same structure:

| File | Responsibility |
|---|---|
| `models.py` | SQLAlchemy ORM table definitions only — no logic |
| `repositories.py` | DB queries — takes `AsyncSession`, returns models/primitives |
| `services.py` | Business logic — orchestrates repos + outbox, no HTTP |
| `schemas.py` | Pydantic request/response shapes — never expose ORM models via API |
| `api.py` | FastAPI `APIRouter` — calls services, maps HTTP status codes |
| `events.py` | Event dataclasses + EventBus handler registrations |
| `workflows/` | Temporal workflow and activity definitions |

Cross-domain reads: query the exposed SQL view by name — never the underlying table.
Cross-domain writes: publish to the outbox in the same transaction as the business operation.

---

## Inter-Domain Communication Patterns

**Pattern 1 — SQL views** (preferred for reads): Domain B exposes a named view; Domain A queries it by name.

**Pattern 2 — Outbox events** (preferred for async reactions):
1. Business op + outbox row written in one DB transaction
2. Background poller dispatches via in-process `EventBus` every 2 seconds
3. All handlers must be **idempotent** — at-least-once delivery

**Pattern 3 — Direct service call** (synchronous, rare): Only when a sync return value is genuinely required. Must have a code comment justifying the exception.

---

## Key Architectural Constraints

- Every table row has `user_id`; every query filters by it. PostgreSQL RLS enforces this as a second layer.
- No PII (phone number, account numbers, card numbers) in application logs.
- Account numbers never stored in full — only `last4` in plaintext; full numbers AES-256 encrypted if ever needed.
- Fingerprint deduplication on transactions: `SHA-256(lower(trim(description)) + date.isoformat() + str(amount))`, unique per `(user_id, fingerprint)`.
- Temporal workflows must be deterministic — no side effects inside workflow code, only in activities.

---

## Tech Stack

| Technology | Role |
|---|---|
| Python 3.13 + FastAPI | HTTP API, SSE streaming |
| PostgreSQL | Sole datastore (no Redis, no secondary DB) |
| Google ADK | AI categorisation agent (tool-use, multi-turn per classification job) |
| Temporal | Durable workflow orchestration (human-in-the-loop, scheduled jobs) |
| Twilio | OTP SMS delivery |
| Alembic | DB migrations — one domain per file, reviewed before committing |
| Ruff | Linting + formatting |
| mypy (strict) | Static type checking |
| uv | Package management |

---

## Development Commands

```bash
uv run python main.py          # Start dev server
uv run alembic upgrade head    # Apply migrations
uv run pytest                  # Run tests
uv run ruff check .            # Lint
uv run mypy src/               # Type check
```

---

## Where to Look First

| Question | File |
|---|---|
| What does a domain own and how does it communicate? | `docs/domains/{domain}.md` |
| What is the full user journey for a feature? | `docs/slices/{nn}-{name}.md` |
| Why was a technology or design choice made? | `docs/adr/` |
| What tables exist and who owns them? | `docs/data-model.md` |
| How does a Temporal workflow run step-by-step? | `docs/workflows/{workflow}.md` |
| What external APIs exist and who calls them? | `docs/integrations.md` |

