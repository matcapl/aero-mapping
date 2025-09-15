# src/geocode/opencage_geocoder.py

# https://api.opencagedata.com/geocode/v1/json?q=<addr>&key=OPENCAGE_KEY&limit=1

import os
import time
import requests
from typing import Tuple

OPENCAGE_KEY = os.environ.get("OPENCAGE_KEY") or os.environ.get("OPENCAGEDATA_KEY")

def geocode(address: str, timeout: float = 10, max_retries: int = 3) -> Tuple[float, float]:
    """
    Uses OpenCage Geocoding API. Requires OPENCAGE_KEY (or OPENCAGEDATA_KEY).
    Returns (lat, lon)
    """
    if not OPENCAGE_KEY:
        raise RuntimeError("OPENCAGE_KEY not configured (set OPENCAGE_KEY)")

    url = "https://api.opencagedata.com/geocode/v1/json"
    params = {"q": address, "key": OPENCAGE_KEY, "limit": 1}
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise RuntimeError(f"OpenCage network error: {e}")
            time.sleep(0.5 * (2 ** (attempt - 1)))
            continue

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if not results:
                raise ValueError("OpenCage returned no results")
            geometry = results[0].get("geometry", {})
            return float(geometry["lat"]), float(geometry["lng"])
        elif resp.status_code in (402, 429):  # 402 possible for quota/paid plan
            if attempt >= max_retries:
                raise RuntimeError(f"OpenCage rate/quota issue: {resp.status_code}")
            time.sleep(1.0 * attempt)
            continue
        else:
            raise RuntimeError(f"OpenCage HTTP {resp.status_code}: {resp.text}")

