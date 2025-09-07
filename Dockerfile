FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gdal-bin libgdal-dev libpq-dev && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN uv sync
COPY . .
CMD ["uv", "run", "python", "src/pipeline.py"]
