# ADR-0009: Logging with Loguru

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Standard Python `logging` works but requires boilerplate handler/formatter configuration to produce structured output. The alternatives considered were:

- `logging` (stdlib) — verbose config, inconsistent formatter setup across handlers
- `structlog` — structured output, popular in production services, requires a composable processor chain
- `loguru` — structured output with zero config, environment-aware rendering, built-in serialization to JSON

The app needs:
1. Pretty, readable output during local development (colours, level names, file/line context)
2. Structured JSON output in production so Grafana Loki can parse fields (level, message, logger, user_id, request_id, etc.)
3. No log files on disk — stdout only, collected externally
4. A way to bind request-scoped context (user_id, request_id) without threading it through every call

---

## Decision

Use **Loguru** for all application logging.

### Environment behaviour

| Environment | Sink | Format | Level |
|---|---|---|---|
| `dev` | `sys.stdout` | Pretty-print with colours and tracebacks | `DEBUG` |
| `prod` | `sys.stdout` | Structured JSON (`serialize=True`) | `INFO` |

The environment is determined by `Settings.env` (set via `APP_ENV` environment variable). The logger is configured once in `runtime/lifespan.py` at startup — no logging config anywhere else.

### Binding request context

Every inbound HTTP request gets a logger bound with `request_id` and (after auth) `user_id`. This bound logger is stored on the `RequestContext` dataclass and passed to services. Domain code never calls `from loguru import logger` — it uses the logger it receives.

```python
# runtime/middleware.py
with logger.contextualize(request_id=ctx.request_id, user_id=str(ctx.user_id)):
    response = await call_next(request)
```

Services that run outside of a request context (Temporal activities, outbox poller) bind their own minimal context:

```python
bound = logger.bind(workflow_id=workflow_id, domain="investments")
bound.info("valuation_updated", holding_id=str(holding_id))
```

### PII rule

The following values must **never** appear in log messages, structured fields, or exception tracebacks:

- Phone numbers
- Bank account numbers (full or partial beyond last 4 digits)
- Card numbers
- JWT token values
- OTP codes
- AES keys or JWT secrets

Scrubbing is enforced by code review, not by a runtime filter. If a value is sensitive, don't log it — log an opaque ID instead.

---

## Consequences

### Positive

- Zero configuration for pretty dev output
- JSON serialization built-in via `serialize=True`
- `contextualize()` provides request-scoped fields without thread-local hacks
- Loguru intercepts `logging.Logger` calls (stdlib compatibility) so third-party libraries that use `logging` are captured automatically

### Negative / Trade-offs

- Loguru is not stdlib — it's a third-party dependency
- The `contextualize()` context manager is async-friendly but requires discipline: any code path that spawns a new coroutine outside the context must re-bind manually

---

## Alternatives Considered

**structlog**: More composable and testable (processors are pure functions). Steeper setup; requires configuring both structlog and the stdlib `logging` bridge. Loguru handles the stdlib bridge automatically with a one-line intercept.

**stdlib `logging`**: No additional dependency. Requires separate `Formatter`, `Handler`, and `Filter` setup to produce structured JSON. Not worth the boilerplate for a greenfield project.
