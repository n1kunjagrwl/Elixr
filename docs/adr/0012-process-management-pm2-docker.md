# ADR-0012: Process Management — PM2 + Docker

**Date**: 2026-04-18  
**Status**: Accepted

---

## Context

The application consists of several long-running processes that must stay up in production:

- **FastAPI app** (uvicorn) — handles HTTP requests
- **Temporal worker** — runs domain workflows and activities
- **Outbox poller** — background task polling the outbox tables every 2 seconds
- **PostgreSQL** — database
- **Temporal server** — workflow orchestration server
- **Grafana stack** — Loki, Prometheus, Tempo, Grafana, Promtail

These need a supervisor layer that:
- Restarts crashed processes automatically
- Starts all processes on server boot
- Provides log rotation
- Allows individual process restart without affecting others

---

## Decision

Use **Docker Compose** to define and containerise each service, and **PM2** to start, supervise, and manage the Docker Compose stack as processes on the production host.

### Responsibilities

| Tool | Responsibility |
|---|---|
| **Docker Compose** | Defines each service (image, ports, volumes, env vars, health checks, networks) |
| **PM2** | Starts the Docker Compose stack on boot, restarts it if it crashes, rotates logs, provides a management CLI |

### PM2 ecosystem config

`ecosystem.config.js` at the repo root:

```js
module.exports = {
  apps: [
    {
      name: "elixir",
      script: "docker",
      args: "compose up",
      cwd: "/path/to/elixir",
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    }
  ]
}
```

PM2 manages the `docker compose up` process as a single supervised unit. Individual service restarts (e.g., just the FastAPI container) are done via `docker compose restart api`, not PM2.

### Docker Compose service structure

```yaml
services:
  api:           # FastAPI + uvicorn
  temporal-worker:  # Temporal activity/workflow worker
  db:            # PostgreSQL
  temporal:      # Temporal server
  loki:          # Log aggregation
  prometheus:    # Metrics
  tempo:         # Tracing
  grafana:       # Dashboard UI
  promtail:      # Log shipping (tails container stdout → Loki)
```

### Environments

| Environment | How to run |
|---|---|
| **Local dev** | `docker compose up` directly — no PM2 needed |
| **Production** | `pm2 start ecosystem.config.js` on server boot; `pm2 save` to persist on reboot |

### Deployment host

The production host is **TBD** — this decision is pending. Once the hosting target is confirmed, the `ecosystem.config.js` paths and any host-specific setup will be documented here. The PM2 + Docker approach works on any Linux VPS or bare-metal server.

---

## Consequences

### Positive

- PM2 provides restart-on-crash, startup persistence (`pm2 startup`), and `pm2 logs` with built-in log rotation — without writing systemd unit files by hand
- Docker Compose isolates services from the host OS and from each other
- `docker compose up` in dev is identical to production topology — no "works on my machine" surprises
- Individual services can be restarted or scaled independently within Compose

### Negative / Trade-offs

- PM2 is a Node.js tool; it adds a Node.js runtime dependency to the production server (only for PM2 itself — not in application containers)
- PM2 supervises the `docker compose` process, not individual containers — if Docker Compose exits cleanly but a container inside it crashes, PM2 won't automatically detect the inner crash (Docker Compose's own `restart: unless-stopped` policy handles that)
- This approach targets a single production host. If the app needs horizontal scaling across multiple hosts, Docker Swarm or Kubernetes would replace this setup. Revisit at scale.

---

## Alternatives Considered

**systemd service units**: Native to Linux, no extra runtime. More verbose to write and maintain. PM2 provides a better DX for developers already familiar with it.

**Docker Swarm**: Multi-host orchestration built into Docker. Adds complexity not needed at current scale.

**Kubernetes**: Production-grade container orchestration. Significant ops overhead for a single-developer project at this stage. Revisit if the app scales.
