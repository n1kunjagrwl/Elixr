/**
 * PM2 Ecosystem Configuration — Elixir
 *
 * Manages the Docker Compose stack as a single supervised process.
 * PM2 keeps docker compose up running and restarts it if it exits.
 *
 * Usage:
 *   pm2 start ecosystem.config.js          # bring up all containers
 *   pm2 stop elixir                        # bring down (compose down)
 *   pm2 restart elixir                     # restart the stack
 *   pm2 logs elixir                        # tail compose output
 *
 * Prerequisites:
 *   - Docker + Docker Compose v2 installed
 *   - PM2 installed globally (`npm install -g pm2`)
 */

module.exports = {
  apps: [
    {
      name: "elixir",
      script: "docker",
      args: "compose up --build",

      // docker compose up holds the terminal; autorestart keeps it supervised.
      autorestart: true,
      restart_delay: 5000,

      // Log file locations (relative to cwd where `pm2 start` is run).
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
  ],
};
