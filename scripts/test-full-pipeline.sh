#!/bin/bash
set -e

echo "🧪 Testing Full Pipeline"

# Test geocoding
echo "Testing geocoding..."
uv run python -c "from src.geocode.providers import default_manager; print('Geocoding OK')"

# Test discovery
echo "Testing discovery..."
uv run python -c "
import asyncio
from src.geocode.geocode import geocode_address
from src.discovery.discovery import find_suppliers
lat, lon = geocode_address('Bristol, UK')
suppliers = asyncio.run(find_suppliers(lat, lon, 2))
print(f'Discovery OK: {len(suppliers)} suppliers')
"

# Test Docker pipeline
echo "Testing Docker pipeline..."
docker-compose run --rm \
  -e DATABASE_LOCAL_URL="postgresql://a:aeroOne@db:5432/suppliers" \
  -e LOCATIONIQ_KEY="$LOCATIONIQ_KEY" \
  app uv run python -m src.pipeline \
  --address "Bristol, UK" \
  --radius 1

echo "✅ All tests passed!"
