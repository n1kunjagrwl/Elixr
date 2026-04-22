# Elixir — Architecture Overview

Elixir is a multi-user personal finance PWA for tracking expenses, income, investments, and peer balances. It targets Indian users (INR primary, multi-currency with conversion) and supports all major investment instrument types. Users upload bank or credit card statements or log transactions manually; an AI agent categorises transactions, asks for clarification when uncertain, and builds a running picture of where money comes from and where it goes — across categories, accounts, and any user-defined time period.

Elixir is an **expense and income tracking tool**, not a bank account manager or net worth calculator. It does not connect to banks, does not sync live account balances, and does not calculate taxes. Account labels exist solely to name a transaction source and track which statement date ranges have been imported.

This is the entry point for the documentation. Read it first, then follow the links to go deeper.

---

## System Diagram

```mermaid
graph TB
    Client["PWA Client\n(Browser / Installed App)"]

    subgraph "Elixir — Single Deployable"
        direction TB
        Runtime["runtime/\nHTTP · Middleware · Startup"]
        Domains["domains/\n12 Domain Packages"]
        Shared["shared/\nEventBus · Outbox · Base · Exceptions"]
        Platform["platform/\nSecurity · DB · Temporal · Clients"]
        Clients["platform/clients/\nExternal API Adapters"]
    end

    subgraph "Infrastructure"
        PG[("PostgreSQL")]
        Temp["Temporal Server"]
        FS["File Storage\n(local / S3-compatible)"]
    end

    subgraph "External Services"
        Twilio["Twilio\n(OTP SMS)"]
        AMFI["AMFI\n(MF NAVs — free)"]
        Eodhd["Eodhd\n(NSE/BSE stocks)"]
        CoinGecko["CoinGecko\n(Crypto prices)"]
        TwelveData["Twelve Data\n(US stocks)"]
        MetalsAPI["metals-api\n(Gold price)"]
        FXApi["exchangerate-api\n(FX rates)"]
    end

    Client <-->|"HTTPS + SSE"| Runtime
    Runtime --> Domains
    Domains --> Shared
    Domains -->|"injected via FastAPI DI"| Clients
    Shared --> Platform
    Platform --> PG
    Platform --> Temp
    Platform --> FS
    Temp -->|"Temporal Activities call"| Clients
    Clients --> Twilio & AMFI & Eodhd & CoinGecko & TwelveData & MetalsAPI & FXApi
```

---

## Architecture Pattern: Modular Monolith

Elixir is a **single deployable unit** structured internally as 12 independent domain packages. There are no microservices and no inter-service network hops. Each domain:

- owns its own database tables — no other domain may write to them directly
- exposes SQL views for cross-domain read-only queries
- publishes domain events when its state changes in a way other domains must react to
- subscribes to events published by other domains via the in-process `EventBus`

This gives the clean domain isolation of microservices without the operational overhead. If a domain ever needs to be extracted into an independent service, the contracts (events, views, service interfaces) are already defined — only the transport changes. See [ADR-0001](adr/0001-modular-monolith.md).

---

## Internal Layer Structure

All application code lives in `src/elixir/` split into four packages:

| Package | What it is | Responsibility |
|---|---|---|
| `runtime/` | How the app runs | Settings (config), FastAPI app factory, middleware pipeline, startup/shutdown lifecycle, DI composition root |
| `platform/` | Infrastructure adapters | Security (JWT, bcrypt, AES-256), DB engine + session factory, Temporal client, file storage (TBD), external API clients |
| `shared/` | Domain-safe utilities | EventBus, outbox poller, SQLAlchemy base + mixins, RequestContext, exceptions, pagination — no secrets, no config |
| `domains/` | All business logic | 12 self-contained domain packages |

**The rules domains must follow**:
- Import from `shared/` and (via DI) `platform/clients/` only
- Never import from `runtime/` — this makes domain services testable without a running HTTP server
- Never import `Settings` or any `platform/security` primitive directly — receive what you need as constructor arguments
- Never import from another domain's `models`, `services`, or `repositories`

See [ADR-0008](adr/0008-runtime-platform-shared-layers.md) and [project-structure.md](project-structure.md) for the full import table.

---

## Technology Stack

| Technology | Role | Why |
|---|---|---|
| **FastAPI** (Python 3.13) | HTTP API, SSE streaming | Async-first, native SSE for statement streaming, Pydantic validation, auto OpenAPI docs |
| **PostgreSQL** | Sole datastore | ACID guarantees for financial data, RLS for multi-tenant security, JSONB, pg_trgm for search — no extra infra needed |
| **Google ADK** | AI categorisation agent | Tool-use capability lets the agent look up categories and ask the user questions mid-workflow; stateful multi-turn per job |
| **Temporal** | Durable workflow orchestration | Human-in-the-loop signals, scheduled jobs, crash-safe resume, built-in Temporal UI for visibility |
| **Twilio** | OTP SMS delivery | Reliable carrier routing in India, delivery receipts, retry handling |
| **PWA** | Frontend | Single codebase for mobile and desktop, installable on home screen, no App Store |
| **pdfplumber + camelot** | PDF parsing | `pdfplumber` for text-layer PDFs; `camelot` for table-heavy or borderline scanned PDFs |
| **Loguru** | Application logging | Structured JSON to stdout in prod (collected by Loki), pretty-print in dev; no file sinks; PII-safe by convention |
| **Grafana stack** | Observability | Loki (log aggregation) + Prometheus (metrics) + Tempo (distributed traces); self-hosted via Docker Compose |
| **OpenTelemetry** | Instrumentation | OTel SDK instruments FastAPI, SQLAlchemy, and HTTP clients; exports traces to Tempo, metrics to Prometheus |
| **GitHub Actions** | CI/CD | Lint → type-check → test → build on every PR; deploy on merge to `main` |
| **Docker + Docker Compose** | Containerisation | All services (API, Temporal worker, PostgreSQL, Grafana stack) run in containers |
| **PM2** | Process management (prod) | Starts and supervises Docker Compose services on the production host; restart-on-crash, log rotation |
| **Alembic** | DB schema migrations | Autogenerate draft migrations, always reviewed and edited before committing; one domain per file |
| **Ruff** | Linting + formatting | Fast Python linter and formatter; enforces import rules and code style in CI |
| **mypy** | Static type checking | Strict type annotations across all layers; catches interface mismatches before runtime |
| **uv** | Package management | Fast, reproducible lockfile, already configured |

---

## Inter-Domain Communication

Three patterns, in preference order. Using pattern 3 requires explicit justification in code.

### Pattern 1 — SQL Views (read-only cross-domain queries)

When Domain A needs to *read* data owned by Domain B for display or aggregation:

- Domain B defines a named SQL view (e.g. `categories_for_user`, `user_accounts_summary`)
- Domain A queries that view by name using raw SQL — it never references Domain B's underlying tables
- Domain B can restructure its tables freely as long as the view contract stays stable

### Pattern 2 — Domain Events via Outbox (async, durable)

When Domain A completes an operation and Domain B must react asynchronously:

```
1. Domain A writes its event to its own `outbox` table
   IN THE SAME DB TRANSACTION as the business operation
   → if the business operation rolls back, the event row rolls back too — atomicity guaranteed

2. A background poller (shared/outbox.py) reads unprocessed rows every 2 seconds
   and dispatches each event to the shared in-process EventBus

3. Domain B's registered handler runs
   → on success: outbox row is marked `processed`
   → on crash between dispatch and mark: row is re-dispatched on next poll
   → therefore: all event handlers MUST be idempotent
```

See [ADR-0003](adr/0003-outbox-pattern.md).

### Pattern 3 — Direct Service Call (synchronous, explicitly justified)

Only when a synchronous return value is genuinely required and an event-driven approach is impossible. Must be accompanied by a code comment explaining the justification. Should be rare across the codebase.

---

## Key Domain Events

| Publisher | Event | Primary Consumers |
|---|---|---|
| `identity` | `UserRegistered` | _(future: onboarding)_ |
| `identity` | `UserLoggedIn` | _(audit only — no consumers)_ |
| `accounts` | `AccountLinked` | `notifications` |
| `accounts` | `AccountRemoved` | `investments` |
| `statements` | `StatementUploaded` | _(audit only — no consumers)_ |
| `statements` | `ExtractionCompleted` | `transactions`, `notifications` |
| `transactions` | `TransactionCreated` | `earnings`, `investments`, `budgets` |
| `transactions` | `TransactionCategorized` | `budgets` |
| `transactions` | `TransactionUpdated` | `budgets` |
| `categorization` | `CategoryCreated` | _(audit only — no consumers)_ |
| `earnings` | `EarningRecorded` | _(audit only — no consumers)_ |
| `earnings` | `EarningClassificationNeeded` | `notifications` |
| `investments` | `SIPDetected` | `notifications` |
| `investments` | `SIPLinked` | _(audit only — no consumers)_ |
| `investments` | `ValuationUpdated` | _(future: planning)_ |
| `budgets` | `BudgetLimitWarning` | `notifications` |
| `budgets` | `BudgetLimitBreached` | `notifications` |
| `import_` | `ImportBatchReady` | `transactions` |
| `import_` | `ImportCompleted` | `notifications` |

---

## Security Model

- Every table row carries `user_id`; every query filters by it — no row is accessible without the authenticated user's ID
- PostgreSQL Row-Level Security (RLS) enforces this at the database layer as a second line of defence
- **JWT sessions**: 15-minute access token, 7-day refresh token in an HttpOnly cookie
- **OTP**: 60-second expiry, max 3 attempts, 5-minute lockout on exhaustion
- Bank account numbers and card numbers stored AES-256 encrypted; only `last4` digits in plaintext
- Uploaded statement files stored at user-scoped paths — never publicly accessible URLs
- No PII (phone number, account numbers, card numbers) written to application logs

---

## Working Principle

> **Confirm before implementing.** No feature, tech stack choice, file placement, domain design, or tooling decision is built until it is explicitly approved. If something is not documented as a confirmed decision in these docs or an ADR, it does not get written into code. Assumptions are not acceptable.

This applies to AI-assisted development as much as to human development. If a question arises mid-implementation ("should this go in `shared/` or `platform/`?", "which logging library?"), stop and ask — don't guess.

---

## Navigation

| Document | What it covers |
|---|---|
| [data-model.md](data-model.md) | Tables per domain, cross-domain ID references, data ownership rules |
| [integrations.md](integrations.md) | Every external API: purpose, rate limits, owning domain, fallback |
| [project-structure.md](project-structure.md) | Full directory tree, layer import rules, domain package conventions |
| [domains/](domains/) | One file per domain: tables, events, views, service methods, key decisions |
| [workflows/](workflows/) | Step-by-step Temporal workflow descriptions |
| [adr/](adr/) | Architecture Decision Records — the *why* behind every major decision |
