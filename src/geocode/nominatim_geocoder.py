# src/geocode/nominatim_geocoder.py
import time
import requests
from typing import Tuple

USER_AGENT = "my-org-name/aero-mapping (contact: dev@example.com)"  # set to your app & contact
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

class GeocodingError(RuntimeError):
    pass

# keep simple rate-limiting per-process (Nominatim public instance: max 1 req/sec)
_last_request_time = 0.0
_LOCK = None  # optional: use threading.Lock() in multithreaded environment

def _ensure_rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_request_time = time.time()

def geocode(address: str, timeout: float = 10, max_retries: int = 3) -> Tuple[float, float]:
    params = {"q": address, "format": "json", "limit": 1, "addressdetails": 0}
    headers = {"User-Agent": USER_AGENT}
    attempt = 0
    while True:
        attempt += 1
        _ensure_rate_limit()
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise GeocodingError(f"Nominatim network error: {e}")
            backoff = 0.5 * (2 ** (attempt - 1))
            time.sleep(backoff)
            continue

        if resp.status_code == 200:
            data = resp.json()
            if not data:
                raise GeocodingError("Nominatim returned empty result")
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            return lat, lon
        elif resp.status_code in (429, 503):
            # respect server-side throttling; back off longer
            if attempt >= max_retries:
                raise GeocodingError(f"Nominatim rejected request, status={resp.status_code}")
            time.sleep(1.0 * attempt)
            continue
        else:
            raise GeocodingError(f"Nominatim HTTP {resp.status_code}: {resp.text}")
