/**
 * PM2 Ecosystem Configuration — Elixir
 *
 * Usage:
 *   pm2 start ecosystem.config.js          # start all apps
 *   pm2 start ecosystem.config.js --env production
 *   pm2 stop all
 *   pm2 logs
 *
 * Prerequisites: PM2 installed globally (`npm install -g pm2`)
 */

module.exports = {
  apps: [
    // -------------------------------------------------------------------------
    // App 1: FastAPI HTTP server
    // -------------------------------------------------------------------------
    {
      name: "elixir-api",
      script: "uv",
      args: "run uvicorn elixir.runtime.app:create_app --factory --host 0.0.0.0 --port 8000 --workers 2",

      // Restart the process if it exceeds this memory ceiling.
      max_memory_restart: "500M",

      // Wait 3 seconds before restarting after a crash (avoids tight restart loops).
      restart_delay: 3000,

      // Log file locations (relative to cwd where `pm2 start` is run).
      out_file: "logs/api-out.log",
      error_file: "logs/api-err.log",

      // Merge stdout + stderr into a single log file as well.
      merge_logs: true,

      env: {
        NODE_ENV: "development",
        PYTHONPATH: "src",
      },

      env_production: {
        NODE_ENV: "production",
        PYTHONPATH: "src",
      },
    },

    // -------------------------------------------------------------------------
    // App 2: Temporal worker
    // -------------------------------------------------------------------------
    {
      name: "elixir-worker",
      script: "uv",
      args: "run python -m elixir.platform.worker",

      max_memory_restart: "500M",
      restart_delay: 3000,

      out_file: "logs/worker-out.log",
      error_file: "logs/worker-err.log",
      merge_logs: true,

      env: {
        NODE_ENV: "development",
        PYTHONPATH: "src",
      },

      env_production: {
        NODE_ENV: "production",
        PYTHONPATH: "src",
      },
    },
  ],
};
