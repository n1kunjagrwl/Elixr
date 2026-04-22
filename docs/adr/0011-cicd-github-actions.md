# ADR-0011: CI/CD — GitHub Actions

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

The project needs automated checks on every pull request (linting, type checking, tests, Docker build) and an automated deployment pipeline triggered on merge to `main`. The code is hosted on GitHub.

---

## Decision

Use **GitHub Actions** for all CI/CD workflows.

### Workflows

#### `ci.yml` — runs on every pull request to `main`

```
Steps (in order, each must pass before the next runs):
1. Lint          → ruff check src/ tests/
2. Format check  → ruff format --check src/ tests/
3. Type check    → mypy src/
4. Unit tests    → pytest tests/unit/ -x --tb=short
5. Integration tests → pytest tests/integration/ -x --tb=short
                       (spins up a test PostgreSQL container via Docker service)
6. Docker build  → docker build . --no-cache (confirms the image builds cleanly)
```

The integration test step uses a PostgreSQL container as a GitHub Actions service. Alembic migrations are applied fresh at the start of the test session (`conftest.py` → `alembic upgrade head`).

#### `deploy.yml` — runs on push to `main` (i.e., after PR merge)

```
Steps:
1. Build Docker image and tag with git SHA
2. Push to container registry (TBD — pending deployment decision)
3. Deploy to production host (TBD — pending deployment decision)
```

The deploy workflow is intentionally left partially defined until the hosting target is confirmed. Steps 2 and 3 will be filled in once deployment is decided.

### Branch protection rules

- `main` is a protected branch
- Merges require: passing `ci.yml` + at least 1 approving review
- No direct pushes to `main` — all changes go through PRs
- No force-pushes to `main`

### Secrets

All sensitive values are stored as GitHub repository secrets (not in code or `.env` files committed to the repo):

| Secret | Used by |
|---|---|
| `DATABASE_URL` | Integration tests |
| `JWT_SECRET` | Integration tests |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Mocked in tests; real values used in deploy |
| `CONTAINER_REGISTRY_TOKEN` | `deploy.yml` image push |

`.env` files are gitignored. A `.env.example` with placeholder values is committed for local dev setup reference.

---

## Consequences

### Positive

- CI runs on every PR — broken code never merges to `main`
- Ruff enforces consistent style and import order; mypy catches type errors before runtime
- Integration tests with a real PostgreSQL DB prevent mock/prod divergence (learned lesson from past projects)
- GitHub-native — no extra tooling to set up or maintain

### Negative / Trade-offs

- Free tier has concurrency limits (1 concurrent job on free); may slow down CI if multiple PRs are open simultaneously
- Deploy workflow is incomplete until hosting is decided — this is intentional, not a gap

---

## Alternatives Considered

**GitLab CI**: Only relevant if the repo were on GitLab. The repo is on GitHub. Ruled out.

**CircleCI / Buildkite**: No meaningful advantage over GitHub Actions for this repo size and team. Additional SaaS dependency. Ruled out.
