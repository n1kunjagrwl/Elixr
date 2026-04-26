#!/usr/bin/env bash
# scripts/install.sh — one-shot bootstrap for Elixr
#
# Installs:
#   1. uv              (Python package/env manager)
#   2. Python deps     (via uv sync --dev)
#   3. Node.js + npm   (required for PM2)
#   4. PM2             (process manager)
#   5. Temporal CLI    (local dev server + tctl)
#
# Usage:
#   bash scripts/install.sh
#   make install

set -euo pipefail

# ── Helpers ───────────────────────────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

info()    { echo -e "${BOLD}[install]${RESET} $*"; }
success() { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
die()     { echo -e "${RED}[✗]${RESET} $*" >&2; exit 1; }

# Detect OS
OS="$(uname -s)"
ARCH="$(uname -m)"

# ── 1. uv ─────────────────────────────────────────────────────────────────────

info "Checking uv..."
if command -v uv &>/dev/null; then
    success "uv $(uv --version | awk '{print $2}') already installed"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for this script session
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    success "uv installed"
fi

# ── 2. Python dependencies ────────────────────────────────────────────────────

info "Installing Python dependencies..."
uv sync --dev
success "Python dependencies installed"

# ── 3. Node.js ────────────────────────────────────────────────────────────────

info "Checking Node.js..."
if command -v node &>/dev/null; then
    NODE_VER="$(node --version)"
    success "Node.js $NODE_VER already installed"
else
    info "Installing Node.js via nvm..."
    if command -v nvm &>/dev/null; then
        nvm install --lts
    elif [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
        brew install node
    elif [ "$OS" = "Linux" ]; then
        # Install via NodeSource (LTS)
        curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
        sudo apt-get install -y nodejs
    else
        die "Cannot install Node.js automatically on $OS. Install it manually from https://nodejs.org and re-run."
    fi
    success "Node.js $(node --version) installed"
fi

# ── 4. PM2 ────────────────────────────────────────────────────────────────────

info "Checking PM2..."
if command -v pm2 &>/dev/null; then
    success "PM2 $(pm2 --version) already installed"
else
    info "Installing PM2 globally..."
    npm install -g pm2
    success "PM2 $(pm2 --version) installed"
fi

# ── 5. Temporal CLI ───────────────────────────────────────────────────────────

info "Checking Temporal CLI..."
if command -v temporal &>/dev/null; then
    success "Temporal CLI $(temporal --version 2>&1 | head -1) already installed"
else
    info "Installing Temporal CLI..."

    TEMPORAL_VERSION="latest"

    if [ "$OS" = "Darwin" ] && command -v brew &>/dev/null; then
        brew install temporal
        success "Temporal CLI installed via Homebrew"

    elif [ "$OS" = "Darwin" ]; then
        # macOS without Homebrew — download binary
        if [ "$ARCH" = "arm64" ]; then
            TEMPORAL_ARCH="arm64"
        else
            TEMPORAL_ARCH="amd64"
        fi
        TEMPORAL_URL="https://temporal.download/cli/archive/latest?platform=darwin&arch=${TEMPORAL_ARCH}"
        TMPDIR_TC="$(mktemp -d)"
        curl -fsSL "$TEMPORAL_URL" -o "$TMPDIR_TC/temporal.tar.gz"
        tar -xzf "$TMPDIR_TC/temporal.tar.gz" -C "$TMPDIR_TC"
        sudo mv "$TMPDIR_TC/temporal" /usr/local/bin/temporal
        rm -rf "$TMPDIR_TC"
        success "Temporal CLI installed to /usr/local/bin/temporal"

    elif [ "$OS" = "Linux" ]; then
        if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            TEMPORAL_ARCH="arm64"
        else
            TEMPORAL_ARCH="amd64"
        fi
        TEMPORAL_URL="https://temporal.download/cli/archive/latest?platform=linux&arch=${TEMPORAL_ARCH}"
        TMPDIR_TC="$(mktemp -d)"
        curl -fsSL "$TEMPORAL_URL" -o "$TMPDIR_TC/temporal.tar.gz"
        tar -xzf "$TMPDIR_TC/temporal.tar.gz" -C "$TMPDIR_TC"
        sudo mv "$TMPDIR_TC/temporal" /usr/local/bin/temporal
        rm -rf "$TMPDIR_TC"
        success "Temporal CLI installed to /usr/local/bin/temporal"

    else
        warn "Cannot auto-install Temporal CLI on $OS."
        warn "Download it manually from: https://docs.temporal.io/cli#install"
    fi
fi

# ── 6. Project scaffold ───────────────────────────────────────────────────────

info "Setting up project directories..."
mkdir -p logs uploads
success "logs/ and uploads/ created"

info "Checking .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env created from .env.example — fill in the required values before starting."
else
    success ".env already exists"
fi

# ── 7. Alembic migrations (if DB is reachable) ───────────────────────────────

info "Attempting database migrations..."
if uv run alembic upgrade head 2>/dev/null; then
    success "Database migrations applied"
else
    warn "Could not connect to the database — run 'make migrate' once it's available."
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}${GREEN}Installation complete.${RESET}"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your credentials"
echo "    2. make dev         — start local API + Temporal dev-server"
echo "    3. make start       — start with PM2 (production)"
echo "    4. make test        — run unit tests"
echo ""
