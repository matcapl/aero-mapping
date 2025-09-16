FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for geospatial libraries
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (better caching)
COPY pyproject.toml uv.lock ./

# Install uv and sync dependencies
RUN pip install uv
RUN uv sync

# Copy source code
COPY . .

# Set PYTHONPATH to find src module
ENV PYTHONPATH=/app

# Default command
CMD ["uv", "run", "python", "-m", "src.pipeline"]
