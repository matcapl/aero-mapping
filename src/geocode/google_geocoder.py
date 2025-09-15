# src/geocode/google_geocoder.py
import os
import requests
from typing import Tuple

GOOGLE_API_KEY = os.environ.get("GOOGLE_GEOCODING_API_KEY")
GOOGLE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
USER_AGENT = "my-org-name/aero-mapping (contact: dev@example.com)"

class GeocodingError(RuntimeError):
    pass

def geocode(address: str, timeout: float = 10, max_retries: int = 3) -> Tuple[float, float]:
    if not GOOGLE_API_KEY:
        raise GeocodingError("Google API key not configured (set GOOGLE_GEOCODING_API_KEY)")
    params = {"address": address, "key": GOOGLE_API_KEY}
    headers = {"User-Agent": USER_AGENT}

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(GOOGLE_URL, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise GeocodingError(f"Google network error: {e}")
            time.sleep(0.5 * (2 ** (attempt - 1)))
            continue

        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            if status == "OK":
                loc = data["results"][0]["geometry"]["location"]
                return float(loc["lat"]), float(loc["lng"])
            elif status in ("OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"):
                if attempt >= max_retries:
                    raise GeocodingError(f"Google quota/limit reached: {status}")
                time.sleep(1.0 * attempt)
                continue
            elif status == "ZERO_RESULTS":
                raise GeocodingError("Google returned zero results")
            else:
                raise GeocodingError(f"Google geocode error: {status}")
        else:
            raise GeocodingError(f"Google HTTP {resp.status_code}: {resp.text}")
