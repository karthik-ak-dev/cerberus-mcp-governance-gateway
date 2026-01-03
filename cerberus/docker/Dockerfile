# Cerberus API Docker Image
# Optimized multi-stage build for minimal image size
#
# =============================================================================
# Build & Run Commands
# =============================================================================
#
# LOCAL (with docker-compose):
#   cd cerberus/docker
#   docker-compose up --build
#
# STAGE:
#   docker build --target stage -t cerberus:stage -f cerberus/docker/Dockerfile cerberus/
#   docker run --env-file cerberus/env/stage.env -p 8000:8000 cerberus:stage
#
# PROD:
#   docker build --target prod -t cerberus:prod -f cerberus/docker/Dockerfile cerberus/
#   docker run --env-file cerberus/env/prod.env -p 8000:8000 cerberus:prod
#

# =============================================================================
# Builder stage - compile dependencies (slim has pre-built wheels)
# =============================================================================
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install production dependencies into a virtual environment
COPY requirements-prod.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-prod.txt

# =============================================================================
# Builder stage for local dev (includes dev dependencies)
# =============================================================================
FROM python:3.11-slim AS builder-dev

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Runtime base - minimal slim image (no build tools)
# =============================================================================
FROM python:3.11-slim AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Only runtime dependencies (libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -g 1000 appgroup \
    && useradd -u 1000 -g appgroup -s /bin/sh appuser

# =============================================================================
# Local development stage
# =============================================================================
FROM runtime-base AS local

COPY --from=builder-dev /opt/venv /opt/venv

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Staging stage - production deps, moderate workers
# =============================================================================
FROM runtime-base AS stage

COPY --from=builder /opt/venv /opt/venv

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# =============================================================================
# Production stage - optimized for size and security
# =============================================================================
FROM runtime-base AS prod

COPY --from=builder /opt/venv /opt/venv

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
