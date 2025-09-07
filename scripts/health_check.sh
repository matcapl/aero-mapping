#!/usr/bin/env bash
set -e
source .env

check_db() {
  URL=$1
  NAME=$2
  echo -n "Checking $NAME DB... "
  psql "$URL" -c "SELECT 1" >/dev/null
  echo "OK"
}

echo "🚑 Health Check"
check_db "$DATABASE_LOCAL_URL" "Local"
check_db "$DATABASE_NEON_URL" "Remote"
curl -s "$NOMINATIM_URL?q=test&format=json" >/dev/null && echo "Nominatim OK"
curl -s -X POST "$OVERPASS_URL" -d "[out:json];node(around:1,0,0)[industrial];out;" >/dev/null && echo "Overpass OK"
echo "✔ All systems green"
