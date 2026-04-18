# ADR-0002: Temporal for Workflow Orchestration

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Several operations in Elixir are long-running, multi-step, and cannot afford to lose state if the server restarts:

1. **Statement processing**: may pause for hours (or days) waiting for a user to classify ambiguous transactions. Must resume from exactly where it paused if the server restarts.
2. **OTP delivery**: must retry delivery with backoff if Twilio is temporarily unavailable. The retry state should survive a server crash.
3. **Investment valuation**: must fetch prices from 5+ external APIs on a schedule, with per-source retry logic and visibility into which runs succeeded or failed.
4. **Import processing**: may pause waiting for the user to confirm column mapping.
5. **Recurring transaction detection**: a weekly batch job that processes every user.

These requirements share a common pattern: durable execution with retry logic, state that survives crashes, and the ability to pause and wait for external input (either a user action or a scheduled time).

---

## Decision

Use **Temporal** as the workflow orchestration engine for all durable workflows and scheduled jobs.

---

## Consequences

### Positive

- **Crash-safe execution.** Temporal's event-sourcing model replays workflow history after a crash. A statement processing workflow that paused waiting for a user to classify row #47 will resume at row #47 after a server restart — not from the beginning.
- **Human-in-the-loop via signals.** Temporal's `wait_for_signal` primitive is purpose-built for pausing a workflow until an external event arrives (a user submitting a classification). Without Temporal, implementing this durably requires a state machine in the DB and polling logic — significantly more complex.
- **Built-in retry policies.** Each Temporal activity has configurable retry policies (maximum attempts, initial interval, backoff coefficient, non-retryable error types). No custom retry logic to write.
- **Scheduled workflows as first-class citizens.** Temporal's scheduler replaces cron jobs with durable, visible, retryable schedules. If the server is down at 02:00 when the recurring detection job should run, Temporal fires it when the server comes back.
- **Temporal UI for visibility.** Every workflow run is visible in the Temporal web UI: current status, history, pending activities, signal history. This is invaluable for debugging stuck statement processing jobs.

### Negative / Trade-offs

- **Additional infrastructure.** Temporal requires its own server (Temporal cluster). For local development, this means running `docker compose up temporal` alongside the app. For production, it means operating or subscribing to Temporal Cloud.
- **Learning curve.** Temporal's programming model (deterministic workflow code, activities, signals, queries) is different from typical async code. Developers must understand why non-determinism in workflow code is forbidden and how to handle it.
- **Workflow code must be deterministic.** `random()`, `datetime.now()`, and direct API calls are not allowed inside workflow functions — they must be in activities. This is a common footgun for new Temporal users.

---

## Alternatives Considered

**Celery + Redis**: Popular Python task queue. Handles background tasks and retries. Does not support: human-in-the-loop (no native signal/wait primitive), durable workflow state (if the worker crashes mid-task, state is lost), or scheduled workflows with visibility. Ruled out because human-in-the-loop is a core requirement for statement processing.

**APScheduler / cron**: Handles scheduled jobs only. No retry logic, no durability, no visibility, no human-in-the-loop. Ruled out.

**Custom DB-backed state machine**: Could implement the statement processing pause/resume as a state machine in PostgreSQL with a poller. This is possible but requires significant custom code for what Temporal provides out of the box (durability, retries, visibility, signals). Ruled out as reinventing Temporal poorly.

**Temporal Cloud**: Managed Temporal service — eliminates the need to operate the Temporal server. A good option for production. The decision to self-host vs. use Temporal Cloud is an operations concern, not an architecture concern.
