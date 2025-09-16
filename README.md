# Aerospace Supplier Mapping Platform

Enterprise-grade supplier discovery using OpenStreetMap data and multiple geocoding providers.

## Quick Start
### Start Docker services
docker-compose up -d --build

### Run discovery pipeline
docker-compose run --rm
-e DATABASE_LOCAL_URL="postgresql://a:aeroOne@db:5432/suppliers"
-e LOCATIONIQ_KEY="your_key"
app uv run python -m src.pipeline
--address "Bristol, UK"
--radius 10
--verbose

## Features
- **Multi-Provider Geocoding**: 6 geocoding services with intelligent failover
- **Industrial Supplier Discovery**: Overpass API integration for manufacturing facilities
- **Spatial Database**: PostGIS-powered proximity analysis
- **Docker Ready**: Full containerization with health checks

## Documentation
- [Development Setup](docs/development/setup-steps.md)
- [Performance Benchmarks](docs/development/performance-benchmarks.md)
- [Docker Deployment](docs/deployment/docker-setup.md)