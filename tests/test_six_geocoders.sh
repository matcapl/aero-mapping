#!/usr/bin/env bash
# tests/test_six_geocoders.sh
# Connectivity & simple-response checks for six geocoder providers.

set -euo pipefail

# Load .env if present
if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

# Test addresses (choose one by uncommenting for your tests)
# TEST_ADDR="Buckingham Palace, London SW1A 1AA, UK"
# TEST_ADDR="Tower of London, London EC3N 4AB, UK"
# TEST_ADDR="Bristol Zoo Gardens, Clifton, Bristol BS8 3HA, UK"
# TEST_ADDR="Manchester Town Hall, Albert Square, Manchester M2 5DB, UK"
# TEST_ADDR="Edinburgh Castle, Castlehill, Edinburgh EH1 2NG, UK"
# TEST_ADDR="Principality Stadium, Westgate Street, Cardiff CF10 1NS, UK"
# TEST_ADDR="Oxford University Museum of Natural History, Parks Road, Oxford OX1 3PW, UK"
# TEST_ADDR="King's College, King's Parade, Cambridge CB2 1ST, UK"
# TEST_ADDR="Royal Albert Dock, Liverpool L3 4AD, UK"
# TEST_ADDR="Glasgow Cathedral, Castle Street, Glasgow G4 0QZ, UK"

# Default test address if none selected
TEST_ADDR="${TEST_ADDR:-10 Downing Street, London, SW1A 2AA, UK}"

# URL-encode the address (keeps it safe even with quotes/spaces)
ENC_ADDR=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${TEST_ADDR}")

has_jq=0
if command -v jq >/dev/null 2>&1; then
  has_jq=1
fi

# ----------------------------
# Track results
# ----------------------------
NOMINATIM_OK=""
GOOGLE_OK=""
MAPBOX_OK=""
HERE_OK=""
LOCATIONIQ_OK=""
OPENCAGE_OK=""

# _do_curl(ipv_flag, url, optional_header)
# header should be passed as a single string like: "User-Agent: me@example.com"
_do_curl() {
  local ipv_flag="$1"; shift
  local url="$1"; shift
  local header="${1:-}"; shift || true

  set +e
  local resp
  if [ -n "${header}" ]; then
    # pass header safely quoted to curl
    resp=$(curl "${ipv_flag}" --silent --show-error --write-out "\n%{http_code}" -H "${header}" "${url}" 2>&1)
  else
    resp=$(curl "${ipv_flag}" --silent --show-error --write-out "\n%{http_code}" "${url}" 2>&1)
  fi
  local exitcode=$?
  set -e

  if [ $exitcode -ne 0 ]; then
    echo "  CURL_ERROR: ${resp}"
    export HTTP_CODE="0"
    export HTTP_BODY=""
    return 2
  fi

  export HTTP_CODE=$(printf "%s\n" "${resp}" | tail -n1)
  export HTTP_BODY=$(printf "%s\n" "${resp}" | sed '$d')

  echo "  HTTP_CODE=${HTTP_CODE}"
  if [ "${has_jq}" -eq 1 ]; then
    printf "%s\n" "${HTTP_BODY}" | jq -C '.' 2>/dev/null || printf "%s\n" "${HTTP_BODY}" | head -n6
  else
    printf "%s\n" "${HTTP_BODY}" | head -n6
  fi
}

echo "TEST ADDRESS: ${TEST_ADDR}"
echo "User-Agent for Nominatim: ${NOMINATIM_USER_AGENT:-aero-mapping-test/1.0 (dev@example.com)}"
echo

# ----------------------------
# Nominatim
# ----------------------------
# Use URL from .env if set, otherwise default
NOMINATIM_BASE_URL="${NOMINATIM_URL:-https://nominatim.openstreetmap.org/search}"
NOMINATIM_USER_AGENT="${NOMINATIM_USER_AGENT:-aero-mapping-test/1.0 (me@mydomain.com)}"
NOMINATIM_OK="FAIL"

for IPFLAG in "-4" "-6"; do
    echo "== Nominatim (${IPFLAG}) =="
    NOMINATIM_URL="${NOMINATIM_BASE_URL}?q=${ENC_ADDR}&format=json&limit=1"
    # pass header as single argument, quoted inside _do_curl
    _do_curl "${IPFLAG}" "${NOMINATIM_URL}" "User-Agent: ${NOMINATIM_USER_AGENT}"

    if [ "${HTTP_CODE:-0}" = "200" ] && [ -n "${HTTP_BODY:-}" ] && [ "${HTTP_BODY}" != "[]" ]; then
        NOMINATIM_OK="OK"
    fi
done
NOMINATIM_OK=${NOMINATIM_OK:-FAIL}
echo

# ----------------------------
# Google
# ----------------------------
if [ -z "${GOOGLE_GEOCODING_API_KEY:-}" ]; then
  echo "SKIP Google: GOOGLE_GEOCODING_API_KEY not set"
  GOOGLE_OK="SKIPPED"
else
  GOOGLE_URL="https://maps.googleapis.com/maps/api/geocode/json?address=${ENC_ADDR}&key=${GOOGLE_GEOCODING_API_KEY}"
  for IPFLAG in "-4" "-6"; do
    echo "== Google (${IPFLAG}) =="
    _do_curl "${IPFLAG}" "${GOOGLE_URL}" ""
    if [ "${HTTP_CODE:-0}" = "200" ] && [ -n "${HTTP_BODY:-}" ]; then
        GOOGLE_OK="OK"
    fi
  done
  GOOGLE_OK=${GOOGLE_OK:-FAIL}
fi
echo

# ----------------------------
# Mapbox
# ----------------------------
if [ -z "${MAPBOX_TOKEN:-}" ]; then
  echo "SKIP Mapbox: MAPBOX_TOKEN not set"
  MAPBOX_OK="SKIPPED"
else
  MAPBOX_URL="https://api.mapbox.com/geocoding/v5/mapbox.places/${ENC_ADDR}.json?access_token=${MAPBOX_TOKEN}&limit=1"
  for IPFLAG in "-4" "-6"; do
    echo "== Mapbox (${IPFLAG}) =="
    _do_curl "${IPFLAG}" "${MAPBOX_URL}" ""
    if [ "${HTTP_CODE:-0}" = "200" ] && [ -n "${HTTP_BODY:-}" ]; then
        MAPBOX_OK="OK"
    fi
  done
  MAPBOX_OK=${MAPBOX_OK:-FAIL}
fi
echo

# ----------------------------
# HERE
# ----------------------------
if [ -z "${HERE_API_KEY:-}" ]; then
  echo "SKIP HERE: HERE_API_KEY not set"
  HERE_OK="SKIPPED"
else
  HERE_URL="https://geocode.search.hereapi.com/v1/geocode?q=${ENC_ADDR}&apiKey=${HERE_API_KEY}"
  for IPFLAG in "-4" "-6"; do
    echo "== HERE (${IPFLAG}) =="
    _do_curl "${IPFLAG}" "${HERE_URL}" ""
    if [ "${HTTP_CODE:-0}" = "200" ] && [ -n "${HTTP_BODY:-}" ]; then
        HERE_OK="OK"
    fi
  done
  HERE_OK=${HERE_OK:-FAIL}
fi
echo

# ----------------------------
# LocationIQ
# ----------------------------
if [ -z "${LOCATIONIQ_KEY:-}" ]; then
  echo "SKIP LocationIQ: LOCATIONIQ_KEY not set"
  LOCATIONIQ_OK="SKIPPED"
else
  LOCATIONIQ_URL="https://us1.locationiq.com/v1/search.php?key=${LOCATIONIQ_KEY}&q=${ENC_ADDR}&format=json&limit=1"
  for IPFLAG in "-4" "-6"; do
    echo "== LocationIQ (${IPFLAG}) =="
    _do_curl "${IPFLAG}" "${LOCATIONIQ_URL}" ""
    if [ "${HTTP_CODE:-0}" = "200" ] && [ -n "${HTTP_BODY:-}" ] && [ "${HTTP_BODY}" != "[]" ]; then
        LOCATIONIQ_OK="OK"
    fi
  done
  LOCATIONIQ_OK=${LOCATIONIQ_OK:-FAIL}
fi
echo

# ----------------------------
# OpenCage
# ----------------------------
if [ -z "${OPENCAGE_KEY:-}" ]; then
  echo "SKIP OpenCage: OPENCAGE_KEY not set"
  OPENCAGE_OK="SKIPPED"
else
  OPENCAGE_URL="https://api.opencagedata.com/geocode/v1/json?q=${ENC_ADDR}&key=${OPENCAGE_KEY}&limit=1"
  for IPFLAG in "-4" "-6"; do
    echo "== OpenCage (${IPFLAG}) =="
    _do_curl "${IPFLAG}" "${OPENCAGE_URL}" ""
    if [ "${HTTP_CODE:-0}" = "200" ] && [ -n "${HTTP_BODY:-}" ] && [ "${HTTP_BODY}" != "[]" ]; then
        OPENCAGE_OK="OK"
    fi
  done
  OPENCAGE_OK=${OPENCAGE_OK:-FAIL}
fi
echo

# ----------------------------
# Summary
# ----------------------------
echo "=== SUMMARY ==="
echo "Nominatim:   ${NOMINATIM_OK}"
echo "Google:      ${GOOGLE_OK}"
echo "Mapbox:      ${MAPBOX_OK}"
echo "HERE:        ${HERE_OK}"
echo "LocationIQ:  ${LOCATIONIQ_OK}"
echo "OpenCage:    ${OPENCAGE_OK}"
echo "================"

echo "Done. HTTP 200=OK, 401/403=auth, 429=rate-limited, connection errors=network."
