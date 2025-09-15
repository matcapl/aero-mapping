# src/geocode/here_geocoder.py

# https://geocode.search.hereapi.com/v1/geocode?q=<addr>&apiKey=HERE_API_KEY

import os
import time
import requests
from typing import Tuple

HERE_API_KEY = os.environ.get("HERE_API_KEY")

def geocode(address: str, timeout: float = 10, max_retries: int = 3) -> Tuple[float, float]:
    """
    Synchronous GET to HERE Geocoding API v1.
    Requires HERE_API_KEY in environment.
    Returns (lat, lon)
    Raises RuntimeError / requests exceptions on failure.
    """
    if not HERE_API_KEY:
        raise RuntimeError("HERE_API_KEY not configured (set HERE_API_KEY)")

    url = "https://geocode.search.hereapi.com/v1/geocode"
    params = {"q": address, "apiKey": HERE_API_KEY, "limit": 1}
    attempt = 0
    while True:
        attempt += 1
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as e:
            if attempt >= max_retries:
                raise RuntimeError(f"HERE network error: {e}")
            time.sleep(0.5 * (2 ** (attempt - 1)))
            continue

        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if not items:
                raise ValueError("HERE returned no result")
            pos = items[0].get("position") or {}
            return float(pos["lat"]), float(pos["lng"])
        elif resp.status_code == 429:
            if attempt >= max_retries:
                raise RuntimeError("HERE rate limited (429)")
            time.sleep(1.0 * attempt)
            continue
        else:
            raise RuntimeError(f"HERE HTTP {resp.status_code}: {resp.text}")
