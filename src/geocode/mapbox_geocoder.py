# src/geocode/mapbox_geocoder.py
import os
import time
import requests
from typing import Tuple

MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", None)
MAPBOX_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json"
USER_AGENT = "my-org-name/aero-mapping (contact: dev@example.com)"

class GeocodingError(RuntimeError):
    pass

def geocode(address: str, timeout: float = 10, max_retries: int = 3) -> Tuple[float, float]:
    if not MAPBOX_TOKEN:
        raise GeocodingError("Mapbox token not configured (set MAPBOX_ACCESS_TOKEN)")
    url = MAPBOX_URL.format(query=requests.utils.requote_uri(address))
    params = {"access_token": MAPBOX_TOKEN, "limit": 1}
    headers = {"User-Agent": USER_AGENT}

    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise GeocodingError(f"Mapbox network error: {e}")
            time.sleep(0.5 * (2 ** (attempt - 1)))
            continue

        if resp.status_code == 200:
            data = resp.json()
            features = data.get("features", [])
            if not features:
                raise GeocodingError("Mapbox returned empty result")
            # Mapbox uses [lon, lat] coordinates in center/geometry
            coords = features[0]["center"]
            lon, lat = float(coords[0]), float(coords[1])
            return lat, lon
        elif resp.status_code == 429:
            # rate limited: back off
            if attempt >= max_retries:
                raise GeocodingError("Mapbox rate limited (429).")
            time.sleep(1.0 * attempt)
            continue
        else:
            raise GeocodingError(f"Mapbox HTTP {resp.status_code}: {resp.text}")
