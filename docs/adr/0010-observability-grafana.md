# ADR-0010: Observability — Grafana Stack (Loki + Prometheus + Tempo)

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

A production finance app needs visibility into three signals:

1. **Logs** — what happened and why (structured, searchable)
2. **Metrics** — how the system is performing (latency, throughput, error rates)
3. **Traces** — where time is spent inside a request (DB queries, external API calls, Temporal activities)

The options considered:

- **Sentry** — error tracking + basic performance. Managed SaaS. Quick to set up but limited metrics and no log aggregation. Costs money at scale.
- **Grafana Cloud (managed)** — hosted Loki + Prometheus + Tempo. Good DX, vendor-neutral OTel export. Has a generous free tier but adds a managed external dependency.
- **Self-hosted Grafana stack** — Loki + Prometheus + Tempo running in Docker Compose alongside the app. Zero vendor lock-in. Full control. Slightly more ops work to bootstrap, but Docker Compose makes it straightforward.

---

## Decision

Use the **self-hosted Grafana stack**: Loki (logs) + Prometheus (metrics) + Tempo (traces), running in Docker Compose.

Instrumentation uses the **OpenTelemetry SDK** — vendor-neutral by design. This means if the team ever wants to switch the backend (e.g., to Grafana Cloud or Honeycomb), only the exporter endpoint changes, not the instrumentation code.

### Stack components

| Component | Role | How data gets there |
|---|---|---|
| **Loki** | Log aggregation + search | Loguru writes JSON to stdout; Promtail (or Alloy) tails container stdout and pushes to Loki |
| **Prometheus** | Metrics collection | FastAPI exposes `/metrics` (Prometheus format); Prometheus scrapes on a 15s interval |
| **Tempo** | Distributed tracing | OTel SDK in FastAPI exports traces via OTLP to Tempo |
| **Grafana** | Unified UI | Single dashboard for logs, metrics, and traces with correlated views |

### Instrumentation points

- **FastAPI**: `opentelemetry-instrumentation-fastapi` — auto-traces every HTTP request (span per route, HTTP status, request duration)
- **SQLAlchemy**: `opentelemetry-instrumentation-sqlalchemy` — traces every DB query (table, operation, duration)
- **HTTP clients** (httpx/aiohttp): `opentelemetry-instrumentation-httpx` — traces outbound calls to Twilio, market data APIs, etc.
- **Temporal activities**: manually instrumented — each activity starts a child span with workflow ID and activity name
- **Custom metrics**: domain-level counters and histograms (transaction count by category, statement extraction duration, budget alert count)

### Trace propagation

Every inbound HTTP request gets a `trace_id`. This ID is:
- Added to the `RequestContext` dataclass
- Injected into Loguru's `contextualize()` so every log line for the request carries `trace_id`
- Propagated to Temporal activities via workflow metadata so the full request → workflow → activity chain is traceable in Tempo

### Key dashboards (to be built)

- **API health**: P50/P95/P99 request latency, error rate by route, active DB connections
- **Domain events**: outbox queue depth, events published per domain, handler error rate
- **Temporal**: workflow run counts, activity failure rates, task queue lag
- **Business**: transaction count per day, statement upload success rate, budget alert frequency

### Local development

The full Grafana stack runs locally via `docker compose up`. Developers can use Grafana at `http://localhost:3000` to inspect logs, metrics, and traces for requests they just made. This is the same stack as production — no "fake" local observability.

---

## Consequences

### Positive

- Single pane of glass: logs, metrics, and traces are correlated in Grafana (click a trace → see the log lines for that request)
- OTel SDK means zero re-instrumentation if backend changes
- Self-hosted = no data leaves the infrastructure, which matters for a finance app handling transaction data
- Local dev observability is identical to production — no surprises

### Negative / Trade-offs

- Docker Compose adds ~4 additional containers (Loki, Prometheus, Tempo, Grafana, Promtail/Alloy) — more RAM and disk on the dev machine
- Grafana dashboards must be built and maintained; not automatic
- Tempo requires a storage backend (local filesystem is fine for dev; object storage needed for prod — pending deployment decision)

---

## Alternatives Considered

**Sentry**: Fast to set up. Does not cover metrics or log aggregation. Would still need Prometheus for metrics and Loki for logs — three separate tools with no correlation. Ruled out.

**Grafana Cloud**: Same stack, managed. No ops burden for hosting. However, structured log data and trace data would be sent to a third party. For a financial app, self-hosting is preferable. Revisit if ops burden becomes a problem.

**Datadog / New Relic**: Expensive at scale, vendor lock-in. Overkill for this project stage.
