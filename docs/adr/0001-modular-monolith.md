# ADR-0001: Modular Monolith over Microservices

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Elixir has 12 distinct functional domains (identity, accounts, statements, transactions, categorisation, earnings, investments, budgets, peers, notifications, FX, import). These domains have clear boundaries — each owns its own data and has well-defined interactions with others. This makes the system a natural candidate for domain-driven design.

The question is whether those 12 domains should be deployed as 12 independent services (microservices) or as one application with strong internal boundaries (modular monolith).

The development team is small. Infrastructure complexity that is acceptable at 50 engineers is a serious cost at 1–3 engineers. The user base is not yet known — a personal finance app could serve tens of users or tens of thousands; the architecture should not assume either extreme.

---

## Decision

Build Elixir as a **single deployable FastAPI application**, internally structured as 12 domain packages. Each domain is a Python package with its own models, services, repositories, event handlers, and Temporal workflows. Cross-domain access is via explicit contracts only (SQL views, domain events via outbox, and rare justified direct service calls).

---

## Consequences

### Positive

- **One service to deploy.** One Docker image, one process to monitor, one set of logs. Infrastructure complexity is proportional to the team size.
- **Shared DB transaction support.** Operations that span two domains can be wrapped in a single `AsyncSession` transaction, guaranteeing atomicity. This is impossible across separate services without distributed transaction protocols.
- **No network overhead between domains.** A request that touches `transactions`, `budgets`, and `notifications` in one user action does not make 3 HTTP calls — it runs in-process.
- **Simple local development.** One `uvicorn` process, one PostgreSQL instance, one Temporal server. Developers can run the entire system locally without a service mesh or Docker Compose for every domain.
- **Easier observability.** One application means one structured log stream, one set of metrics, one trace context per request.

### Negative / Trade-offs

- **All domains must be deployed together.** A bug in `notifications` requires redeploying the entire application, even if the bug is isolated. This is mitigated by a robust test suite and staged rollouts.
- **Cannot scale domains independently.** If the investments valuation workflow consumes significant CPU, it cannot be scaled separately from the HTTP API. Mitigation: Temporal workers can be deployed as a separate process pointing to the same Temporal server, allowing horizontal scaling of background work.
- **Domain isolation is enforced by convention and code review, not by network boundaries.** A developer can accidentally import across domain boundaries. Mitigation: linting rules (`import-linter` or `pylint`) that enforce the domain boundary rules.

---

## Alternatives Considered

**Full microservices (12 services)**: Each domain becomes an independent FastAPI service. Benefits: true isolation, independent scaling, independent deployments. Costs: service discovery, inter-service authentication, distributed tracing, network latency on every cross-domain call, complex local development. The operational burden for a small team far outweighs the benefits at this scale.

**Traditional monolith (no domain enforcement)**: One FastAPI application where modules can freely call each other's functions. Simple to build initially, but becomes unmaintainable as the codebase grows — every change has unpredictable ripple effects. Ruled out because the financial domain complexity guarantees this becomes a problem within months.

---

## Migration Path

The modular monolith is designed to be extractable. If a domain needs independent scaling or deployment:

1. Replace its in-process `EventBus` subscriptions with a real message broker (Kafka or RabbitMQ)
2. Replace shared DB access with a domain-specific database and expose the SQL views as API endpoints
3. Deploy the domain as a standalone FastAPI service

The contracts (events, view interfaces, service method signatures) are already defined — only the transport layer changes.
