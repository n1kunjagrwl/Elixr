/**
 * PM2 Ecosystem Configuration — Elixir
 *
 * Two processes:
 *
 *   elixir         — the full Docker Compose stack (production/staging).
 *                    Runs postgres, temporal, api, worker, and the nginx
 *                    client in a single supervised docker compose up.
 *
 *   elixir-client  — Vite dev server (development only, port 5173).
 *                    Use alongside `make dev` (FastAPI + Temporal).
 *                    Do NOT run alongside the docker stack — they conflict.
 *
 * Usage:
 *   pm2 start ecosystem.config.js                         # production stack
 *   pm2 start ecosystem.config.js --only elixir-client    # client dev only
 *   pm2 stop elixir                                       # bring down stack
 *   pm2 logs elixir-client                                # tail client logs
 *   pm2 delete elixir-client                              # remove client process
 *
 * Prerequisites:
 *   - Docker + Docker Compose v2 (for the elixir process)
 *   - Node 20 + npm (for elixir-client)
 *   - PM2 installed globally: npm install -g pm2
 */

module.exports = {
  apps: [
    // ── Production: full Docker Compose stack ──────────────────────────────
    {
      name: "elixir",
      script: "docker",
      args: "compose up --build",

      // docker compose up blocks the terminal; PM2 keeps it supervised.
      autorestart: true,
      restart_delay: 5000,

      out_file: "logs/compose-out.log",
      error_file: "logs/compose-err.log",
      merge_logs: true,

      env: {
        NODE_ENV: "development",
      },
      env_production: {
        NODE_ENV: "production",
      },
    },

    // ── Development: Vite client dev server (port 5173) ────────────────────
    {
      name: "elixir-client",
      script: "npm",
      args: "run dev",
      cwd: "./client",

      // Vite watches files itself; PM2 watch would double-restart.
      watch: false,
      autorestart: true,
      restart_delay: 2000,

      out_file: "logs/client-out.log",
      error_file: "logs/client-err.log",
      merge_logs: true,

      env_development: {
        NODE_ENV: "development",
      },
    },
  ],
};
