# =============================================================================
# Elixir — Multi-stage Dockerfile
# =============================================================================
# Stage 1 (builder): install dependencies into an isolated virtualenv with uv.
# Stage 2 (runtime): copy only the virtualenv and application source — no build
#                    tooling lands in the final image.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: builder
# -----------------------------------------------------------------------------
FROM python:3.13-slim AS builder

WORKDIR /app

# Install uv (fast Python package manager).
# Pinning the install script version keeps builds reproducible.
RUN pip install --no-cache-dir uv

# Copy dependency manifests first so Docker can cache the install layer.
COPY pyproject.toml uv.lock ./

# Install production dependencies into /app/.venv using the locked lockfile.
# --frozen  : fail if uv.lock is out of date (guarantees reproducibility)
# --no-dev  : skip development/test dependencies
RUN uv sync --frozen --no-dev

# Copy the rest of the application source.
COPY . .


# -----------------------------------------------------------------------------
# Stage 2: runtime
# -----------------------------------------------------------------------------
FROM python:3.13-slim

WORKDIR /app

# Install curl for the HEALTHCHECK — keep the layer minimal.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built virtualenv from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# Copy the application source.
COPY --from=builder /app/src ./src
COPY --from=builder /app/alembic ./alembic
COPY --from=builder /app/alembic.ini ./alembic.ini

# Put the virtualenv's bin/ directory first so `uvicorn`, `alembic`, etc.
# are resolved without activating the virtualenv explicitly.
ENV PATH="/app/.venv/bin:$PATH"

# Make the source tree importable as a package root.
ENV PYTHONPATH="/app/src"

# Non-root user for security — run the process as `appuser`.
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check: the /health endpoint must return HTTP 2xx within 30 s.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "elixir.runtime.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
