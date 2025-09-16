# Development Setup Steps

## Database Setup
psql "$DATABASE_LOCAL_URL" -c "SELECT PostGIS_Version();"
psql "$DATABASE_NEON_URL" -c "SELECT PostGIS_Version();"

## Discovery Evolution Testing
Basic discovery (170 suppliers)
uv run python - <<EOF
from src.discovery.discovery import find_suppliers

... your test code

**docs/development/performance-benchmarks.md** - Your timing results
Performance Benchmarks
Discovery Module Evolution
discovery.py: 170 suppliers, basic query

discovery_filter.py: 878 suppliers, filtered

discovery_filter_and_deduplication.py: 598 suppliers, deduplicated

discovery_async_caching.py: 598 suppliers in 28.11s (no reverse geocoding)

discovery_async_caching.py: 598 suppliers in 875.54s (with reverse geocoding)

sortAndDedupFirst.py: 597 suppliers in 521.36s (optimized)

**docs/deployment/docker-setup.md** - Your Docker journey
Docker Deployment Guide
Database Schema Initialization
bash
docker-compose exec db psql -U a -d suppliers -c "
CREATE EXTENSION IF NOT EXISTS postgis;