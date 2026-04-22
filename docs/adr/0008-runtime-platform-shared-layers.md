# ADR-0008: Three-Layer Internal Structure (runtime / platform / shared)

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

The original plan grouped all non-domain infrastructure into a single `core/` package:

```
src/elixir/
├── core/
│   ├── db.py
│   ├── events.py
│   ├── outbox.py
│   ├── temporal.py
│   ├── security.py
│   └── config.py
├── domains/
└── app.py
```

`core/` is a common Python pattern that starts clean and becomes a dumping ground. It conflates three genuinely distinct concerns:

1. **How the app runs** (FastAPI assembly, middleware, startup hooks) — `app.py`
2. **What external systems the app depends on** (DB engine, Temporal client, Twilio, API clients) — `db.py`, `temporal.py`
3. **Infrastructure utilities that domains can use** (security, config, event bus, base models) — `security.py`, `events.py`, `config.py`

The problem: a domain importing from `core/` has implicit access to `app.py`, `temporal.py`, and any other module in the package — including FastAPI's `Request` object and the Temporal worker factory. This makes it impossible to:
- Test domain services without starting the HTTP layer
- Know what a domain actually depends on without reading all its imports
- Swap an external system (e.g., replace Eodhd with a different stock API) without touching domain code

---

## Decision

Replace `core/` with three explicitly separated packages inside `src/elixir/`:

| Package | What it contains |
|---|---|
| `runtime/` | Settings (config), FastAPI app factory, middleware pipeline, lifespan hooks (startup/shutdown), FastAPI dependency functions |
| `platform/` | Security utilities (JWT, bcrypt, AES-256), DB engine + session factory, Temporal client, external API clients |
| `shared/` | EventBus, outbox poller, SQLAlchemy base + mixins, RequestContext, common exceptions, pagination schemas |

**Why config belongs in `runtime/`, not `shared/`**: `Settings` is only safe to read at startup — it reads from environment variables and `.env` files. If it lived in `shared/`, any domain could do `from elixir.shared.config import settings` and bypass the injection rule. Placing it in `runtime/` makes that import impossible: `runtime/` is never imported by domains.

**Why security belongs in `platform/`, not `shared/`**: JWT signing, bcrypt hashing, and AES-256 encryption are infrastructure-level operations that depend on secrets (JWT secret key, AES key) passed in from config at startup. They fit `platform/` — a layer of external-system adapters and security primitives — rather than `shared/`, which should contain utilities that are genuinely secret-free (base classes, event bus, exception types).

With this import rule table:

| Layer | May import from | Must NOT import from |
|---|---|---|
| `runtime/` | `platform/`, `shared/`, `domains/` | — |
| `platform/` | stdlib + third-party only | `runtime/`, `shared/`, `domains/` |
| `shared/` | stdlib + third-party only | `runtime/`, `platform/`, `domains/` |
| `domains/{x}/` | `shared/`, injected `platform/clients/` | `runtime/`, `platform/` directly, `domains/{y}/` internals |

**How domains get settings values**: `runtime/dependencies.py` assembles whatever the domain service needs and passes it via constructor injection. A domain service never calls `Settings()` or imports from `runtime/`. It receives a concrete value (a `str`, a `bool`, a typed config sub-object) through its constructor.

```python
# runtime/dependencies.py
def get_identity_service(
    session: AsyncSession = Depends(get_db_session),
    twilio: TwilioClient = Depends(get_twilio_client),
    settings: Settings = Depends(get_settings),
) -> IdentityService:
    return IdentityService(session=session, twilio=twilio, jwt_secret=settings.jwt_secret)

# domains/identity/services.py — Settings is never imported here
class IdentityService:
    def __init__(self, session: AsyncSession, twilio: TwilioClient, jwt_secret: str):
        ...
```

External API clients (`platform/clients/`) are injected into domain services via FastAPI dependency injection — they are never imported directly by domain code.

---

## Consequences

### Positive

- **Domain services are testable without the HTTP layer.** A unit test for `transactions.services.create_transaction()` needs: an `AsyncSession` mock and any injected clients. It does not need a FastAPI `TestClient` or a running application.
- **External system boundaries are explicit.** `platform/` contains every external system adapter. When replacing a market data API, the change is isolated to one file in `platform/clients/` and the DI wiring in `runtime/app.py`. Domain code is untouched.
- **Startup logic is in one place.** `runtime/lifespan.py` is the single file where the DB connection pool opens, the Temporal client connects, and the outbox poller starts. No startup logic is buried in module-level code inside `core/`.
- **New developers know where code belongs.** The three-layer naming is self-explanatory. "This is a new external API" → `platform/clients/`. "This is a new background utility domains can use" → `shared/`. "This is a new middleware" → `runtime/`.

### Negative / Trade-offs

- **More folders to navigate.** `core/db.py` becomes `platform/db.py`. An extra level of mental mapping for new contributors.
- **Dependency injection wiring overhead.** Every external client that a domain service needs must be threaded through FastAPI's DI system (`Depends()`). This is more explicit but slightly more boilerplate than a direct import. Mitigated by creating typed dependency functions in each domain's `api.py` that hide the DI details from the service layer.

---

## Alternatives Considered

**Flat `core/` with enforced sub-packages** (e.g., `core/runtime/`, `core/platform/`): Adds the same structure inside `core/`. Preferred to skip the intermediate `core/` namespace — it adds a level without meaning. `runtime/`, `platform/`, `shared/` at the top level of `src/elixir/` is cleaner.

**Hexagonal architecture (ports and adapters)**: A more formal version of this separation where every external system interaction is defined as a port (interface) and the concrete adapter is injected. More rigorous isolation, easier mocking. Adds significant interface boilerplate for every client method. Worthwhile at larger scale; premature abstraction at this stage. The current structure is compatible with adding ports later without restructuring.

**Feature folders (collocate infrastructure with domain)**: Each domain owns its own DB session factory, its own Temporal client. Eliminates cross-layer imports entirely but duplicates infrastructure setup and makes shared concerns (the outbox poller, the FX rate service) ambiguous — which domain owns them? Ruled out.
