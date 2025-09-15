# src/geocode/three_geocoder.py
import os
import sqlite3
import time
import asyncio
from typing import Optional, Tuple

from . import nominatim_geocoder, mapbox_geocoder, google_geocoder

CACHE_DB = os.environ.get("GEOCODE_CACHE_DB", "geocode_cache.sqlite3")

class GeocodingError(RuntimeError):
    pass

class SimpleCache:
    def __init__(self, path=CACHE_DB):
        self._path = path
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("""CREATE TABLE IF NOT EXISTS cache (
            address TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            provider TEXT,
            ts INTEGER
        )""")
        self._conn.commit()

    def get(self, address: str) -> Optional[Tuple[float,float,str]]:
        cur = self._conn.execute("SELECT lat, lon, provider FROM cache WHERE address = ?", (address,))
        row = cur.fetchone()
        if row:
            return float(row[0]), float(row[1]), row[2]
        return None

    def set(self, address: str, lat: float, lon: float, provider: str):
        self._conn.execute("INSERT OR REPLACE INTO cache(address,lat,lon,provider,ts) VALUES(?,?,?,?,?)",
                           (address, lat, lon, provider, int(time.time())))
        self._conn.commit()

_cache = SimpleCache()

# default provider order; you can set via env or pass at runtime
DEFAULT_ORDER = os.environ.get("GEOCODER_ORDER", "nominatim,mapbox,google").split(",")

def geocode(address: str, provider_order=None, use_cache=True, **kwargs) -> Tuple[float, float]:
    """
    Synchronous geocode. Returns (lat, lon)
    Tries providers in provider_order until one works.
    """
    provider_order = provider_order or DEFAULT_ORDER
    if use_cache:
        hit = _cache.get(address)
        if hit:
            lat, lon, provider = hit
            return lat, lon

    last_exc = None
    for p in provider_order:
        try:
            if p == "nominatim":
                lat, lon = nominatim_geocoder.geocode(address, **kwargs)
            elif p == "mapbox":
                lat, lon = mapbox_geocoder.geocode(address, **kwargs)
            elif p == "google":
                lat, lon = google_geocoder.geocode(address, **kwargs)
            else:
                continue
            if use_cache:
                _cache.set(address, lat, lon, p)
            return lat, lon
        except Exception as e:
            last_exc = e
            # try next provider
            continue
    raise GeocodingError(f"All providers failed for '{address}': {last_exc}")

async def geocode_async(address: str, *args, **kwargs) -> Tuple[float, float]:
    # run blocking geocode in worker thread
    return await asyncio.to_thread(geocode, address, *args, **kwargs)
