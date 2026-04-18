# ADR-0005: PostgreSQL as the Sole Datastore

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

Elixir's data needs span several patterns:

- **Transactional financial records** (transactions, budgets, earnings): require ACID guarantees and strong consistency
- **Time-series data** (investment valuation_snapshots): one row per holding per day, queried by date range
- **Hot lookup data** (category lists, FX rates): read frequently, change infrequently
- **Full-text search** (searching transactions by description): fuzzy matching on merchant names
- **Event outbox** (domain events): sequential writes, polled reads

A polyglot persistence approach would use a specialised store for each: TimescaleDB for time-series, Redis for caching, Elasticsearch for search, PostgreSQL for transactional data.

---

## Decision

Use **PostgreSQL as the sole datastore** for all data. Rely on PostgreSQL's native capabilities rather than adding specialised stores.

---

## Consequences

### Positive

- **One system to understand, operate, and back up.** The team does not need operational expertise in TimescaleDB, Redis, and Elasticsearch. One database instance, one backup strategy, one connection pool.
- **ACID guarantees across all data.** The outbox pattern relies on writing an event in the same transaction as the business operation. This is only possible because everything is in one database. In a polyglot setup, the outbox and the business data would be in different stores — requiring distributed transaction protocols.
- **No cache invalidation bugs.** There is no Redis cache that could drift out of sync with the PostgreSQL source of truth. Reads always go to the authoritative data.
- **PostgreSQL is more capable than its reputation suggests.** For the scale of a personal finance application serving thousands of users:
  - `pg_trgm` extension handles trigram-based fuzzy search on transaction descriptions without Elasticsearch
  - Partial indexes on `(user_id, date)` make time-range queries on `transactions` fast
  - `valuation_snapshots` at one row per holding per day for 10 holdings over 2 years = ~7,300 rows — well within PostgreSQL's performance envelope
  - `JSONB` handles flexible metadata (notification payload, import error logs) without a separate document store
  - Row-Level Security enforces multi-tenant isolation at the DB layer

### Negative / Trade-offs

- **Higher read latency for hot data.** FX rates and category lists are read on almost every request. Without an in-memory cache, each read hits PostgreSQL. At the expected scale (hundreds to low thousands of concurrent users), this is fine — PostgreSQL handles this easily. At tens of thousands of concurrent users, this becomes worth revisiting.
- **No specialised time-series optimisations.** `valuation_snapshots` is a plain PostgreSQL table, not a TimescaleDB hypertable. For the expected number of holdings and history depth, query performance is adequate. This is the most likely concern to revisit at scale.
- **Full-text search is good but not as powerful as Elasticsearch.** `pg_trgm` handles "find transactions containing 'swiggy'" excellently. It does not handle stemming, synonyms, or semantic search. For this application's search requirements (find transactions by merchant name or description keyword), pg_trgm is sufficient.

---

## When to Revisit

If the user base grows to tens of thousands of active users:

1. **Add Redis** for FX rate and category list caching. These are ideal cache candidates: infrequently written, frequently read, small, and tolerate brief staleness.
2. **Consider TimescaleDB** if `valuation_snapshots` queries become a bottleneck. TimescaleDB is a PostgreSQL extension — the migration is a schema change, not a database swap.
3. **Consider Elasticsearch** if transaction search requirements grow beyond description keyword matching (semantic search, multi-field scoring).

Each of these additions is optional and additive — they do not require rearchitecting the system.

---

## Alternatives Considered

**PostgreSQL + Redis + Elasticsearch**: Full polyglot. Adds operational complexity without meaningful benefit at the current scale. Every additional store is another system that can fail, drift, and require expertise.

**SQLite**: Simpler to operate, no server needed. Ruled out for multi-user concurrent access — SQLite's write serialisation would become a bottleneck immediately. Not suitable for a multi-user application.

**MongoDB**: Document model is flexible but loses ACID transaction guarantees needed for financial data. Aggregations for budget tracking and earning summaries are more complex in MongoDB than PostgreSQL's window functions and CTEs. Ruled out.
