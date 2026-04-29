.DEFAULT_GOAL := help
SHELL         := /bin/bash

# ── Colours ───────────────────────────────────────────────────────────────────
BOLD  := \033[1m
RESET := \033[0m
GREEN := \033[32m
CYAN  := \033[36m

# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help install sync dev start stop restart logs test test-integration \
        lint typecheck migrate migrate-new shell clean

help: ## Show this help
	@echo ""
	@echo "  $(BOLD)Elixr — available targets$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────

install: ## Bootstrap: install uv, PM2, Temporal CLI and all project deps
	@bash scripts/install.sh

sync: ## Install / refresh Python dependencies from uv.lock
	uv sync --dev

# ── Development ───────────────────────────────────────────────────────────────

dev: ## Start API + Temporal dev-server locally (foreground, Ctrl-C to stop)
	@echo "$(BOLD)Starting Temporal dev-server in background...$(RESET)"
	@temporal server start-dev --headless &
	@echo "$(BOLD)Starting FastAPI dev server...$(RESET)"
	uv run uvicorn elixir.runtime.app:create_app --factory \
		--host 0.0.0.0 --port 8000 --reload

# ── Production (PM2) ──────────────────────────────────────────────────────────

start: ## Start all containers with Docker Compose (via PM2)
	pm2 start ecosystem.config.js --env production

stop: ## Stop all containers
	docker compose down
	pm2 stop elixir 2>/dev/null || true

restart: ## Restart all containers
	docker compose down
	pm2 restart elixir 2>/dev/null || pm2 start ecosystem.config.js --env production

logs: ## Tail Docker Compose logs (last 50 lines per service, then follow)
	docker compose logs --tail=50 -f

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Apply all pending Alembic migrations
	uv run alembic upgrade head

migrate-new: ## Create a new Alembic migration (usage: make migrate-new msg="your message")
	uv run alembic revision --autogenerate -m "$(msg)"

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run unit tests (no Docker required)
	uv run pytest tests/domains/ -v

test-integration: ## Run integration tests (requires Docker)
	uv run pytest tests/integration/ -v

test-all: ## Run all tests
	uv run pytest -v

# ── Code quality ──────────────────────────────────────────────────────────────

lint: ## Lint and auto-fix with ruff
	uv run ruff check src/ tests/ --fix
	uv run ruff format src/ tests/

typecheck: ## Static type checking with mypy
	uv run mypy src/

check: lint typecheck ## Run lint + typecheck together

# ── Misc ──────────────────────────────────────────────────────────────────────

shell: ## Open a Python shell with project on PYTHONPATH
	uv run python

clean: ## Remove bytecode caches and build artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache dist build
