a@Mac aero-mapping % 

uv run python - <<EOF            
from src.core.config import settings
print("Remote DB:", settings.database_neon_url)
print("Local DB: ", settings.database_local_url)
print("Nominatim URL:", settings.nominatim_url)
print("Overpass URL:", settings.overpass_url)
EOF

Remote DB: postgresql://neondb_owner:YOUR_SECRET@ep-shiny-frost-abcs9vli-pooler.eu-west-2.aws.neon.tech/suppliers?sslmode=require
Local DB:  postgresql://a:aeroOne@localhost:5432/suppliers
Nominatim URL: https://nominatim.openstreetmap.org/search
Overpass URL: https://overpass-api.de/api/interpreter

chmod +x scripts/create_tables.sh
./scripts/create_tables.sh

psql "$DATABASE_LOCAL_URL" -c "SELECT PostGIS_Version();"
psql "$DATABASE_NEON_URL" -c "SELECT PostGIS_Version();"

source .env && echo $NOMINATIM_URL && echo $OVERPASS_URL

uv run python - <<EOF
import overpy, geopy, asyncpg
print("OK:", overpy.__version__, geopy.__version__)
EOF

codium src/geocode/geocode.py
uv run python - <<EOF
from src.geocode.geocode import geocode_address
print("Bristol:", geocode_address("Bristol, UK"))
EOF

codium src/discovery/discovery.py
uv run python - <<EOF
import asyncio
from src.geocode.geocode import geocode_address
from src.discovery.discovery import find_suppliers
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(find_suppliers(lat, lon, 5))
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--
Count: 170
Sample: [{'name': 'Filton DC Substation', 'address': '', 'lat': Decimal('51.5093914'), 'lon': Decimal('-2.5730055'), 'distance_miles': 0.67, 'source': 'overpass', 'confidence': 0.7}, {'name': 'Filton 20', 'address': '', 'lat': Decimal('51.5100307'), 'lon': Decimal('-2.5829911'), 'distance_miles': 0.69, 'source': 'overpass', 'confidence': 0.7}]

codium src/discovery/discovery_filter.py
uv run python - <<EOF                                     
import asyncio
from src.geocode.geocode import geocode_address
from src.discovery.discovery_filter import find_suppliers
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(find_suppliers(lat, lon, 5))
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--
Count: 878
Sample: [{'name': 'GKN Aerospace', 'address': '', 'lat': Decimal('51.5088406'), 'lon': Decimal('-2.5782844'), 'distance_miles': 0.58, 'source': 'overpass', 'confidence': 0.9}, {'name': 'Unknown', 'address': '', 'lat': Decimal('51.5087086'), 'lon': Decimal('-2.5827187'), 'distance_miles': 0.6, 'source': 'overpass', 'confidence': 0.7}]

codium src/discovery/discovery_filter_and_deduplication.py
uv run python - <<EOF
import asyncio
from src.geocode.geocode import geocode_address
from src.discovery.discovery_filter_and_deduplication import find_suppliers
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(find_suppliers(lat, lon, 5))
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--
Count: 598
Sample: [{'name': 'GKN Aerospace', 'address': '', 'lat': Decimal('51.5088406'), 'lon': Decimal('-2.5782844'), 'distance_miles': 0.58, 'source': 'overpass', 'confidence': 0.9}, {'name': 'Swarf House', 'address': '', 'lat': Decimal('51.5091312'), 'lon': Decimal('-2.5790025'), 'distance_miles': 0.6, 'source': 'overpass', 'confidence': 0.7}]

codium src/discovery/discovery_filter_and_deduplication_async_caching.py
uv run python - <<EOF
import asyncio
import time
from src.geocode.geocode import geocode_address
from src.discovery.discovery_filter_and_deduplication_async_caching import find_suppliers
start_time = time.time()
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(find_suppliers(lat, lon, 5))
elapsed = time.time() - start_time
print(f"Time elapsed: {elapsed:.2f} seconds")
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--
Time elapsed: 28.11 seconds
Count: 598
Sample: [{'name': 'GKN Aerospace', 'address': '', 'lat': Decimal('51.5088406'), 'lon': Decimal('-2.5782844'), 'distance_miles': 0.58, 'source': 'overpass', 'confidence': 0.9}, {'name': 'Swarf House', 'address': '', 'lat': Decimal('51.5091312'), 'lon': Decimal('-2.5790025'), 'distance_miles': 0.6, 'source': 'overpass', 'confidence': 0.7}]

<!-- with reverse_geocoding set = True: -->
Time elapsed: 875.54 seconds
Count: 598
Sample: [{'name': 'GKN Aerospace', 'address': '', 'lat': Decimal('51.5088406'), 'lon': Decimal('-2.5782844'), 'distance_miles': 0.58, 'source': 'overpass', 'confidence': 0.9}, {'name': 'Swarf House', 'address': '', 'lat': Decimal('51.5091312'), 'lon': Decimal('-2.5790025'), 'distance_miles': 0.6, 'source': 'overpass', 'confidence': 0.7}]

codium src/discovery/discovery_filter_and_deduplication_async_caching_transparent.py
uv run python - <<EOF
import asyncio
import time
from src.geocode.geocode import geocode_address
from src.discovery.discovery_filter_and_deduplication_async_caching_transparent import find_suppliers
start = time.time()
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(find_suppliers(lat, lon, 5, deduplicate=True, reverse_geocode=True))
elapsed = time.time() - start
print(f"Time elapsed: {elapsed:.2f} seconds")
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--


codium src/discovery/discovery_filter_and_deduplication_async_caching_log.py
uv run python - <<EOF
import asyncio
import time
from src.geocode.geocode import geocode_address
from src.discovery.discovery_filter_and_deduplication_async_caching_log import find_suppliers
start = time.time()
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(
    find_suppliers(lat, lon, 5, deduplicate=True, reverse_geocode=True)
)
elapsed = time.time() - start
print(f"Time elapsed: {elapsed:.2f} seconds")
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--
Settings: deduplicate=True, reverse_geocode=True, cache=True
Reverse-geocode progress: 10/878
Reverse-geocode progress: 20/878
Reverse-geocode progress: 30/878
...
Reverse-geocode progress: 860/878
Reverse-geocode progress: 870/878
Reverse-geocode progress: 878/878
Time elapsed: 543.89 seconds
Count: 598
Sample: [{'name': 'GKN Aerospace', 'address': '', 'lat': Decimal('51.5088406'), 'lon': Decimal('-2.5782844'), 'distance_miles': 0.58, 'source': 'overpass', 'confidence': 0.9}, {'name': 'Swarf House', 'address': '', 'lat': Decimal('51.5091312'), 'lon': Decimal('-2.5790025'), 'distance_miles': 0.6, 'source': 'overpass', 'confidence': 0.7}]

codium src/discovery/discovery_filter_and_deduplication_async_caching_log_sortAndDedupFirst.py 
uv run python - <<EOF
import asyncio
import time
from src.geocode.geocode import geocode_address
from src.discovery.discovery_filter_and_deduplication_async_caching_log_sortAndDedupFirst import find_suppliers
start = time.time()
lat, lon = geocode_address("Filton, Bristol, UK")
suppliers = asyncio.run(
    find_suppliers(lat, lon, 5, deduplicate=True, reverse_geocode=True)
)
elapsed = time.time() - start
print(f"Time elapsed: {elapsed:.2f} seconds")
print("Count:", len(suppliers))
print("Sample:", suppliers[:2])
EOF
--
Settings: deduplicate=True, reverse_geocode=True, cache=True
Reverse-geocode progress: 10/597
Reverse-geocode progress: 20/597
Reverse-geocode progress: 30/597
...
Reverse-geocode progress: 580/597
Reverse-geocode progress: 590/597
Reverse-geocode progress: 597/597
Time elapsed: 521.36 seconds
Count: 597
Sample: [{'name': 'GKN Aerospace', 'address': '', 'lat': Decimal('51.5088406'), 'lon': Decimal('-2.5782844'), 'distance_miles': 0.56, 'source': 'overpass', 'confidence': 0.9}, {'name': 'Swarf House', 'address': '', 'lat': Decimal('51.5091312'), 'lon': Decimal('-2.5790025'), 'distance_miles': 0.58, 'source': 'overpass', 'confidence': 0.7}]

# testing and expanding to six geocoders
uv run python -c "import sys, pathlib; print('cwd=', pathlib.Path.cwd()); import importlib; importlib.import_module('src.geocode.providers'); print('ok')"

uv run python scripts/check_providers_async.py


codium src/pipeline.py
uv run python -m src.pipeline \
  --address "New Filton House, Filton, Bristol BS99 7AR, UK" \
  --name "Airbus Filton" \
  --radius 10 \
  --verbose

# Verify local DB
psql "$DATABASE_LOCAL_URL" -c "SELECT count(*) FROM facility_suppliers;"
# Verify remote DB
psql "$DATABASE_NEON_URL" -c "SELECT count(*) FROM facility_suppliers;"

codium src/visualize/visualize.py
codium src/pipeline.py

uv run python src/pipeline.py \
  --address "Filton, Bristol, UK" \
  --radius 5

ls -l suppliers.csv map.html

Open map.html in your browser to confirm markers.

codium docker-compose.yml
codium Dockerfile

docker-compose up -d --build

# Wait for db, then
docker-compose exec app bash -c "python src/pipeline.py --address 'Bristol, UK' --radius 5"

# or
docker-compose exec app python src/pipeline.py \
  --address "Filton, Bristol" \
  --name "Airbus Filton" \
  --radius 5

# Check artifacts
docker-compose exec app ls -l suppliers.csv map.html

# Check map locally
open map.html  # macOS; or browse http://localhost:8000 if API endpoint added

codium scripts/health_check.sh
chmod +x scripts/health_check.sh
./scripts/health_check.sh

Summary
This OSM‐based variant requires no paid API keys, minimal registration, and leverages Nominatim + Overpass for geocoding and discovery. Follow the seven steps—Init, DB, Geocode, Discover, Pipeline, Visualize, Deploy—with their three sub‐tasks each. At the end, you will have a working Dockerized MVP that geocodes a Tier-1 facility, discovers nearby Tier-2 suppliers, stores them in PostGIS, exports CSV, and displays an interactive map—all without Google Maps.