#!/usr/bin/env bash
# test_geocoders.sh
# Quick connectivity/health checks for Nominatim, Google Geocoding API, and Mapbox Geocoding API.
# Usage:
#   GOOGLE_API_KEY=... MAPBOX_TOKEN=... ./test_geocoders.sh
#
# Notes:
# - For Nominatim you MUST include a meaningful User-Agent or Referer (see policy).
# - The script will try IPv4 and IPv6 separately (if your system supports them).
# - It prefers jq for nicer JSON checks; will fall back to simple greps if jq is missing.

set -euo pipefail

# ---------------------------
# Config / test address
# ---------------------------
TEST_ADDRESS="1000 Enterprise Way, Bristol BS34 8QZ, UK"
NOMINATIM_USER_AGENT="${NOMINATIM_USER_AGENT:-my-org/aero-mapping (dev@example.com)}"
NOMINATIM_EMAIL="${NOMINATIM_EMAIL:-}"  # optional: include an email in the query when doing larger volumes
GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
MAPBOX_TOKEN="${MAPBOX_TOKEN:-}"

# Tools
HAS_JQ=0
if command -v jq >/dev/null 2>&1; then
  HAS_JQ=1
fi

# Helper to perform curl and capture body + http_code + stderr message
# args: $1 = ipv_flag ("-4" or "-6"), $2 = url, $3 = extra_headers (string), $4 = curl extra params
_do_curl() {
  local ipv_flag="$1"; shift
  local url="$1"; shift
  local headers="$1"; shift
  local extra="$*"

  local errfile
  errfile="$(mktemp)"
  # Capture body with HTTP code on final line
  local resp
  if ! resp=$(curl ${ipv_flag} --fail --show-error --silent --write-out "\n%{http_code}" ${extra} ${headers} "${url}" 2> "${errfile}"); then
    local exitcode=$?
    local err
    err=$(sed -n '1,200p' "${errfile}" | sed 's/^/  /')
    rm -f "${errfile}"
    echo "CURL_FAILED_EXITCODE=${exitcode}"
    echo "CURL_STDERR:"
    echo "${err}"
    return 2
  fi
  rm -f "${errfile}"

  # split resp -> body & http_code
  local http_code
  http_code=$(printf "%s\n" "${resp}" | tail -n1)
  local body
  body=$(printf "%s\n" "${resp}" | sed '$d')

  printf "HTTP_CODE=%s\n" "${http_code}"
  printf "BODY_SUMMARY:\n"
  if [ "${HAS_JQ}" -eq 1 ]; then
    printf "%s\n" "${body}" | jq -C '.' 2>/dev/null || { printf "%s\n" "${body}" | sed -n '1,10p'; }
  else
    # Don't assume jq, print a short snippet
    printf "%s\n" "${body}" | sed -n '1,12p'
  fi

  return 0
}

print_header() {
  printf "\n==== %s ====\n" "$1"
}

# -------------
#  Nominatim
# -------------
test_nominatim() {
  print_header "Nominatim (nominatim.openstreetmap.org)"
  local q
  q=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "${TEST_ADDRESS}")

  local url="https://nominatim.openstreetmap.org/search?q=${q}&format=json&limit=1"
  if [ -n "${NOMINATIM_EMAIL}" ]; then
    url="${url}&email=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${NOMINATIM_EMAIL}")"
  fi

  local header="-H \"User-Agent: ${NOMINATIM_USER_AGENT}\""
  echo "Using User-Agent: ${NOMINATIM_USER_AGENT}"
  echo "NOTE: Nominatim public service expects a valid User-Agent/Referer and is rate-limited (max 1 req/sec)."

  for ipflag in "-4" "-6"; do
    printf "\n-- Nominatim test (curl %s) --\n" "${ipflag}"
    # Call helper
    if ! _do_curl "${ipflag}" "${url}" "${header}"; then
      echo "Nominatim ${ipflag} test: connection/transport error or blocked. Check IPv6 routing or local firewall."
    else
      echo "Nominatim ${ipflag} test: finished (see HTTP_CODE/BODY_SUMMARY above)."
      # Extra interpretation for empty array
      # using jq if available
      if [ "${HAS_JQ}" -eq 1 ]; then
        local found
        found=$(curl ${ipflag} --silent -H "User-Agent: ${NOMINATIM_USER_AGENT}" "${url}" | jq '. | length')
        if [ "${found}" = "0" ]; then
          echo "Nominatim response: empty result ([]) -- no match found or limited permissions/blocked."
        fi
      else
        # quick grep for "[]"
        if curl ${ipflag} --silent -H "User-Agent: ${NOMINATIM_USER_AGENT}" "${url}" | sed -n '1,5p' | grep -q '^\s*\[\s*\]'; then
          echo "Nominatim response: empty JSON array (no results)."
        fi
      fi
    fi
    sleep 1  # be polite; Nominatim expects 1s spacing
  done
}

# -------------
# Google Geocoding
# -------------
test_google() {
  print_header "Google Maps Geocoding API"
  if [ -z "${GOOGLE_API_KEY}" ]; then
    echo "SKIP: GOOGLE_API_KEY is not set. Set GOOGLE_API_KEY env var to test Google Geocoding."
    return
  fi

  local q
  q=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "${TEST_ADDRESS}")
  local url="https://maps.googleapis.com/maps/api/geocode/json?address=${q}&key=${GOOGLE_API_KEY}"

  for ipflag in "-4" "-6"; do
    printf "\n-- Google test (curl %s) --\n" "${ipflag}"
    if ! _do_curl "${ipflag}" "${url}" ""; then
      echo "Google ${ipflag} test: connection/transport error."
    else
      echo "Google ${ipflag} test: finished (see HTTP_CODE/BODY_SUMMARY above)."
      # Check for "status": "OK"
      if [ "${HAS_JQ}" -eq 1 ]; then
        status=$(curl ${ipflag} --silent "${url}" | jq -r '.status // "NO_STATUS"')
        echo "Google JSON status: ${status}"
      else
        curl ${ipflag} --silent "${url}" | sed -n '1,20p' | grep -E '"status"'
      fi
    fi
  done
}

# -------------
# Mapbox Geocoding
# -------------
test_mapbox() {
  print_header "Mapbox Geocoding API"
  if [ -z "${MAPBOX_TOKEN}" ]; then
    echo "SKIP: MAPBOX_TOKEN is not set. Set MAPBOX_TOKEN env var to test Mapbox Geocoding."
    return
  fi
  local q
  q=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "${TEST_ADDRESS}")
  local url="https://api.mapbox.com/geocoding/v5/mapbox.places/${q}.json?access_token=${MAPBOX_TOKEN}&limit=1"

  for ipflag in "-4" "-6"; do
    printf "\n-- Mapbox test (curl %s) --\n" "${ipflag}"
    if ! _do_curl "${ipflag}" "${url}" ""; then
      echo "Mapbox ${ipflag} test: connection/transport error."
    else
      echo "Mapbox ${ipflag} test: finished (see HTTP_CODE/BODY_SUMMARY above)."
      # Check for features length
      if [ "${HAS_JQ}" -eq 1 ]; then
        cnt=$(curl ${ipflag} --silent "${url}" | jq '.features | length')
        echo "Mapbox features count: ${cnt}"
      else
        curl ${ipflag} --silent "${url}" | sed -n '1,20p' | grep -E '"features"'
      fi
    fi
  done
}

# ----------------------
# Run tests
# ----------------------
echo "TEST ADDRESS: ${TEST_ADDRESS}"
test_nominatim
test_google
test_mapbox

echo
echo "Done. Interpret HTTP codes: 200 OK, 403/401 auth or blocked, 429 rate-limit, connection errors indicate routing/firewall/IPv6 problems."
