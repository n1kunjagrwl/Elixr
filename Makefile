.DEFAULT_GOAL := help
SHELL         := /bin/bash

# ── Colours (tput emits real terminal escape bytes; gracefully empty if unsupported) ──
BOLD  := $(shell tput bold 2>/dev/null || true)
RESET := $(shell tput sgr0  2>/dev/null || true)
CYAN  := $(shell tput setaf 6 2>/dev/null || true)

# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help install sync dev dev-all client-install client-dev client-build \
        start stop restart logs test test-integration test-all test-e2e test-e2e-ui \
        lint typecheck check migrate migrate-new shell clean pm2-clean

help: ## Show this help
	@echo ""
	@echo "  $(BOLD)Elixir — available targets$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────

install: ## Bootstrap: install uv, PM2, Temporal CLI and all project deps
	@bash scripts/install.sh
	@$(MAKE) client-install

sync: ## Refresh Python dependencies from uv.lock
	uv sync --dev

# ── Development ───────────────────────────────────────────────────────────────

dev: ## Start API + Temporal dev-server locally (Ctrl-C stops both)
	@temporal server start-dev --headless & TPID=$$!; \
	cleanup() { echo ""; echo "Stopping Temporal..."; kill $$TPID 2>/dev/null || true; }; \
	trap cleanup INT TERM EXIT; \
	echo ""; \
	echo "  $(BOLD)API$(RESET)          http://localhost:8000"; \
	echo "  $(BOLD)API docs$(RESET)     http://localhost:8000/docs"; \
	echo "  $(BOLD)Temporal UI$(RESET)  http://localhost:8088"; \
	echo ""; \
	uv run uvicorn elixir.runtime.app:create_app --factory \
		--host 0.0.0.0 --port 8000 --reload

dev-all: ## Start API + Temporal + Vite client (Ctrl-C stops all)
	@pm2 start ecosystem.config.js --only elixir-client --env development; \
	temporal server start-dev --headless & TPID=$$!; \
	cleanup() { \
		echo ""; \
		echo "Stopping Vite client and Temporal..."; \
		pm2 stop elixir-client 2>/dev/null || true; \
		kill $$TPID 2>/dev/null || true; \
	}; \
	trap cleanup INT TERM EXIT; \
	echo ""; \
	echo "  $(BOLD)Client$(RESET)       http://localhost:5173"; \
	echo "  $(BOLD)API$(RESET)          http://localhost:8000"; \
	echo "  $(BOLD)API docs$(RESET)     http://localhost:8000/docs"; \
	echo "  $(BOLD)Temporal UI$(RESET)  http://localhost:8088"; \
	echo ""; \
	uv run uvicorn elixir.runtime.app:create_app --factory \
		--host 0.0.0.0 --port 8000 --reload

# ── Client (frontend) ─────────────────────────────────────────────────────────

client-install: ## Install frontend npm dependencies
	npm --prefix client install

client-dev: ## Start Vite dev server (frontend, port 5173)
	npm --prefix client run dev

client-build: ## Build frontend for production (output: client/dist/)
	npm --prefix client run build

# ── Production (PM2 + Docker Compose) ────────────────────────────────────────

start: ## Start server (Docker Compose) + client (Vite) via PM2
	pm2 start ecosystem.config.js --env production
	@echo ""
	@echo "  $(BOLD)Client$(RESET)       http://localhost:80"
	@echo "  $(BOLD)API$(RESET)          http://localhost:8000"
	@echo "  $(BOLD)API docs$(RESET)     http://localhost:8000/docs"
	@echo "  $(BOLD)Temporal UI$(RESET)  http://localhost:8088"
	@echo ""

stop: ## Stop all containers, PM2 processes, and flush logs
	docker compose down
	pm2 stop elixir elixir-client 2>/dev/null || true
	pm2 flush 2>/dev/null || true

restart: ## Rebuild images and restart server + client
	docker compose down
	docker compose build
	pm2 delete elixir elixir-client 2>/dev/null || true
	pm2 start ecosystem.config.js --env production

pm2-clean: ## Remove stale PM2 processes not in ecosystem.config.js and save the list
	@echo "Keeping only: elixir, elixir-client"
	@pm2 list --no-color 2>/dev/null \
		| awk '/│/{print $$4}' \
		| grep -Ev '^(elixir|elixir-client|name|$$)' \
		| xargs -r pm2 delete 2>/dev/null || true
	pm2 save

logs: ## Tail logs — container logs when running, PM2 logs otherwise
	@if docker compose ps -q 2>/dev/null | grep -q .; then \
		docker compose logs --tail=50 -f; \
	else \
		echo "No containers running. Showing PM2 logs (docker compose output):"; \
		pm2 logs elixir --lines 100; \
	fi

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Apply all pending Alembic migrations
	uv run alembic upgrade head

migrate-new: ## Create a new Alembic migration (usage: make migrate-new msg="description")
	uv run alembic revision --autogenerate -m "$(msg)"

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run unit tests (no Docker required)
	uv run pytest tests/domains/ -v

test-integration: ## Run integration tests (requires Docker)
	uv run pytest tests/integration/ -v

test-all: ## Run all tests
	uv run pytest -v

test-e2e: ## Run Playwright end-to-end tests (starts Vite automatically)
	cd client && npx playwright test

test-e2e-ui: ## Open Playwright UI for interactive test runs
	cd client && npx playwright test --ui

# ── Code quality ──────────────────────────────────────────────────────────────

lint: ## Lint and auto-fix with ruff
	uv run ruff check src/ tests/ --fix
	uv run ruff format src/ tests/

typecheck: ## Static type checking with mypy
	uv run mypy src/

check: lint typecheck ## Run lint + typecheck together

# ── Misc ──────────────────────────────────────────────────────────────────────

shell: ## Open a Python REPL with project on PYTHONPATH
	uv run python

clean: ## Remove bytecode caches and build artefacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache dist build client/dist
