# ADR-0003: Outbox Pattern for Domain Event Durability

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Domains communicate via events. When Domain A completes an operation, it must notify Domain B. The naive implementation is:

```python
async def create_transaction(...):
    await session.commit()          # business operation completes
    await event_bus.publish(event)  # event is dispatched
```

This has two failure modes:

1. **Server crashes between `commit()` and `publish()`.** The transaction exists in the DB but the event is never dispatched. Domain B never learns about the transaction. Silent data inconsistency.

2. **`publish()` runs before `commit()`.** If Domain B's handler runs immediately and tries to read the new transaction, it may not exist yet. If the commit then fails, the event was dispatched for an operation that never completed.

Both failures are real. PostgreSQL commits are fast but not instantaneous. Server processes can crash at any instruction. A financial application where events drive budget tracking and investment detection cannot afford silent inconsistency.

---

## Decision

Use the **Outbox Pattern**. Domain A writes its event to an `outbox` table row **in the same database transaction** as the business operation. A background poller reads unprocessed outbox rows and dispatches them to the in-process `EventBus`. Event handlers must be **idempotent** (safe to run more than once).

```python
async def create_transaction(session: AsyncSession, ...):
    transaction = Transaction(...)
    session.add(transaction)

    # Written in the SAME transaction — if commit fails, outbox row rolls back too
    outbox_row = Outbox(
        event_type="transactions.TransactionCreated",
        payload=TransactionCreated(...).to_dict(),
        status="pending"
    )
    session.add(outbox_row)

    await session.commit()  # both transaction and outbox row commit atomically
```

The outbox poller (in `shared/outbox.py`) runs as a background asyncio task:

```
Every 2 seconds:
  SELECT * FROM {each domain}.outbox WHERE status = 'pending' ORDER BY created_at LIMIT 100
  For each row:
    dispatch to EventBus
    UPDATE outbox SET status = 'processed', processed_at = now()
```

If the poller crashes between dispatch and the `UPDATE` (the narrow failure window), the row remains `pending` and is re-dispatched on the next poll. This means **at-least-once delivery** — event handlers may receive the same event more than once and must be idempotent.

---

## Consequences

### Positive

- **Atomicity guaranteed.** If the business operation fails and rolls back, the outbox row rolls back with it. No orphaned events.
- **No lost events.** Events committed to the outbox are durable — they survive server crashes. The poller dispatches them when the server restarts.
- **No extra infrastructure.** The outbox table is in the same PostgreSQL database as all other domain data. No Kafka, no RabbitMQ, no Redis Streams.
- **Inspectable.** The outbox table can be queried to see pending events, failed deliveries, and delivery history. Debugging event delivery is a SQL query.

### Negative / Trade-offs

- **2-second latency** between a domain event being committed and it being dispatched to consumers. This is acceptable for all current use cases (budget alerts, notification creation, investment SIP detection). If sub-second event propagation becomes necessary, switch to PostgreSQL `LISTEN/NOTIFY` for immediate notification with outbox as the durable backing store.
- **Handlers must be idempotent.** At-least-once delivery is a requirement on all event handler implementations. Every handler checks whether the effect of the event has already been applied before applying it again (e.g., check if an earnings record already exists for this transaction_id before creating one).
- **Outbox table per domain.** Adds a table to every event-publishing domain. This is a small structural cost that is worth the durability guarantee.
- **Poller is a single point of concern.** If the poller task dies and is not restarted, events accumulate in the outbox indefinitely. The poller must be monitored (health check endpoint checks outbox row age) and restarted automatically (managed by the FastAPI lifespan handler).

---

## Alternatives Considered

**PostgreSQL LISTEN/NOTIFY**: Fast (sub-millisecond notification) and built into PostgreSQL. Does not provide durability — notifications are lost if the listener is not connected when the notification fires. Could be combined with the outbox (NOTIFY triggers the poller instead of waiting for the 2-second interval) but adds complexity for marginal gain.

**Kafka / RabbitMQ**: Production-grade message brokers with at-least-once delivery, durability, and consumer group management. Appropriate at microservice scale. Adds significant infrastructure and operational overhead that is unnecessary for a modular monolith where all consumers share one process.

**Simple publish-after-commit**: Call `event_bus.publish()` after `session.commit()`. No durability, no atomicity. Rules out the moment any failure between commit and publish becomes possible — which is always.
