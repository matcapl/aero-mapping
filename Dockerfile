FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.4.17 /uv /bin/uv
WORKDIR /app
RUN apt-get update && apt-get install -y gdal-bin libgdal-dev libpq-dev build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY . .
RUN uv sync --locked

FROM python:3.11-slim
RUN apt-get update && apt-get install -y gdal-bin libgdal-dev libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "src/pipeline.py"]