# Builder stage: Lock and sync deps with uv
FROM ghcr.io/astral-sh/uv:0.4.18 AS uv

FROM python:3.12-slim AS builder

# Bootstrap uv binary
COPY --from=uv /uv /bin/uv

WORKDIR /app

# Install system deps for GDAL, PostGIS, etc.
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy

# Sync deps: Mount lock/tom for fresh, cache uv downloads
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable

# Add full source, resync project
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

# Runtime stage: Minimal image
FROM python:3.12-slim

WORKDIR /app

# Runtime deps only
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy venv artifact (no source code for security)
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "src/pipeline.py"]