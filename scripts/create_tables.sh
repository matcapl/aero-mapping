#!/usr/bin/env bash
set -e
source .env

# Function to test and setup a given DB URL
setup_db() {
  local URL=$1
  echo "→ Setting up database: $URL"
  PGPASSWORD=$(echo "$URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
  psql "$URL" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
DROP TABLE IF EXISTS facilities, suppliers, facility_suppliers CASCADE;
CREATE TABLE facilities (
  id SERIAL PRIMARY KEY, name TEXT, address TEXT,
  location GEOGRAPHY(POINT,4326), industry_sectors TEXT[],
  created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE suppliers (
  id SERIAL PRIMARY KEY, name TEXT, address TEXT,
  location GEOGRAPHY(POINT,4326), source TEXT, confidence FLOAT, 
  product_category TEXT, md_name TEXT, linkedin_url TEXT,
  companies_house_number TEXT, companies_house_url TEXT,
  customers_list TEXT[], website scraped at TIMESTAMP,
  enrichment_status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE facility_suppliers (
  facility_id INT REFERENCES facilities(id),
  supplier_id INT REFERENCES suppliers(id),
  distance_miles FLOAT, discovered_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (facility_id, supplier_id)
);
CREATE INDEX ON facilities USING GIST(location);
CREATE INDEX ON suppliers USING GIST(location);
SQL
}

# Local DB
setup_db "$DATABASE_LOCAL_URL"
# Remote DB
setup_db "$DATABASE_NEON_URL"
echo "✅ Database setup complete (local and remote)."
