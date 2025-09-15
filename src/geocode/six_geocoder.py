# src/geocode/six_geocoder.py
import os
import sqlite3
import time
import asyncio
from typing import Optional, Tuple

# provider modules (you must implement or adapt these)
from . import nominatim_geocoder, mapbox_geocoder, google_geocoder
from . import here_geocoder, locationiq_geocoder, opencage_geocoder

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
        self._conn.execute(
            "INSERT OR REPLACE INTO cache(address,lat,lon,provider,ts) VALUES(?,?,?,?,?)",
            (address, lat, lon, provider, int(time.time()))
        )
        self._conn.commit()

_cache = SimpleCache()

# default provider order; you can set via env or pass at runtime
DEFAULT_ORDER = os.environ.get(
    "GEOCODER_ORDER",
    "nominatim,mapbox,google,here,locationiq,opencage"
).split(",")

def _call_provider_by_name(name: str, address: str, **kwargs) -> Tuple[float, float]:
    name = name.strip().lower()
    if name == "nominatim":
        return nominatim_geocoder.geocode(address, **kwargs)
    if name == "mapbox":
        return mapbox_geocoder.geocode(address, **kwargs)
    if name == "google":
        return google_geocoder.geocode(address, **kwargs)
    if name == "here":
        return here_geocoder.geocode(address, **kwargs)
    if name == "locationiq":
        return locationiq_geocoder.geocode(address, **kwargs)
    if name == "opencage" or name == "open_cage" or name == "opencagedata":
        return opencage_geocoder.geocode(address, **kwargs)
    raise GeocodingError(f"Unknown provider '{name}'")

def geocode(address: str, provider_order=None, use_cache=True, **kwargs) -> Tuple[float, float]:
    """
    Synchronous geocode. Returns (lat, lon)
    Tries providers in provider_order until one works.
    """
    provider_order = provider_order or DEFAULT_ORDER
    # normalize address key slightly
    key = address.strip()

    if use_cache:
        hit = _cache.get(key)
        if hit:
            lat, lon, provider = hit
            return lat, lon

    last_exc = None
    for p in provider_order:
        try:
            lat, lon = _call_provider_by_name(p, address, **kwargs)
            if use_cache:
                _cache.set(key, lat, lon, p)
            return lat, lon
        except Exception as e:
            last_exc = e
            # try next provider
            continue
    raise GeocodingError(f"All providers failed for '{address}': {last_exc}")

async def geocode_async(address: str, *args, **kwargs) -> Tuple[float, float]:
    # run blocking geocode in worker thread so async code (pipeline) can await it
    return await asyncio.to_thread(geocode, address, *args, **kwargs)
