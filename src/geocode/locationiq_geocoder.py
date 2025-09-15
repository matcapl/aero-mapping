# src/geocode/locationiq_geocoder.py

# https://us1.locationiq.com/v1/search.php?key=LOCATIONIQ_KEY&q=<addr>&format=json&limit=1

import os
import time
import requests
from typing import Tuple

# Note: LocationIQ may use region-specific domains; adjust if your account uses a different host.
LOCATIONIQ_KEY = os.environ.get("LOCATIONIQ_KEY")

def geocode(address: str, timeout: float = 10, max_retries: int = 3) -> Tuple[float, float]:
    """
    Uses LocationIQ search API. Expects LOCATIONIQ_KEY in env.
    Returns (lat, lon)
    """
    if not LOCATIONIQ_KEY:
        raise RuntimeError("LOCATIONIQ_KEY not configured (set LOCATIONIQ_KEY)")

    url = "https://us1.locationiq.com/v1/search.php"
    params = {"key": LOCATIONIQ_KEY, "q": address, "format": "json", "limit": 1}
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise RuntimeError(f"LocationIQ network error: {e}")
            time.sleep(0.5 * (2 ** (attempt - 1)))
            continue

        if resp.status_code == 200:
            data = resp.json()
            if not data:
                raise ValueError("LocationIQ returned empty result")
            # LocationIQ returns a list of results
            top = data[0]
            return float(top["lat"]), float(top["lon"])
        elif resp.status_code in (429, 403):
            if attempt >= max_retries:
                raise RuntimeError(f"LocationIQ rate-limited or blocked: {resp.status_code}")
            time.sleep(1.0 * attempt)
            continue
        else:
            raise RuntimeError(f"LocationIQ HTTP {resp.status_code}: {resp.text}")
