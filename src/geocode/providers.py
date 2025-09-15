# src/geocode/providers.py
import os
import time
import json
import sqlite3
import asyncio
from typing import Tuple, Optional
import httpx
from urllib.parse import quote_plus
from src.core.config import settings

# -------------------------
# Simple sqlite cache helpers (run on thread to avoid blocking)
# -------------------------
CACHE_DB = os.environ.get("GEOCODE_CACHE_DB", "geocode_cache.sqlite3")

def _init_cache_db():
    conn = sqlite3.connect(CACHE_DB, check_same_thread=True)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS geocode_cache (
        address TEXT PRIMARY KEY,
        lat REAL, lon REAL, provider TEXT, ts INTEGER
      )
    """)
    conn.commit()
    conn.close()

# ensure DB exists at import
_init_cache_db()

def _cache_get_sync(address: str):
    conn = sqlite3.connect(CACHE_DB, check_same_thread=True)
    cur = conn.execute("SELECT lat, lon, provider FROM geocode_cache WHERE address = ?", (address,))
    row = cur.fetchone()
    conn.close()
    if row:
        return float(row[0]), float(row[1]), row[2]
    return None

def _cache_set_sync(address: str, lat: float, lon: float, provider: str):
    conn = sqlite3.connect(CACHE_DB, check_same_thread=True)
    conn.execute("INSERT OR REPLACE INTO geocode_cache(address,lat,lon,provider,ts) VALUES(?,?,?,?,?)",
                 (address, lat, lon, provider, int(time.time())))
    conn.commit()
    conn.close()

# -------------------------
# Provider base class (async)
# -------------------------
class GeocodeError(RuntimeError):
    pass

class BaseProvider:
    async def geocode(self, address: str) -> Tuple[float, float]:
        raise NotImplementedError

# -------------------------
# Nominatim provider (async, enforces 1s between calls)
# -------------------------
class NominatimProvider(BaseProvider):
    def __init__(self, base_url: Optional[str] = None, user_agent: Optional[str] = None):
        self.base_url = base_url or settings.nominatim_url.rstrip('/')
        self.user_agent = user_agent or os.environ.get("NOMINATIM_USER_AGENT", "aero-mapping/1.0 (dev@example.com)")
        # rate limit state (per-process)
        self._lock = asyncio.Lock()
        self._last_ts = 0.0

    async def _wait_rate(self):
        async with self._lock:
            now = time.time()
            wait = 1.0 - (now - self._last_ts)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_ts = time.time()

    async def geocode(self, address: str) -> Tuple[float, float]:
        await self._wait_rate()
        url = f"{self.base_url}/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": self.user_agent}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if not data:
                    raise GeocodeError("Nominatim: empty result")
                return float(data[0]["lat"]), float(data[0]["lon"])
            elif resp.status_code in (429, 503):
                raise GeocodeError(f"Nominatim rate-limited: {resp.status_code}")
            else:
                raise GeocodeError(f"Nominatim HTTP {resp.status_code}: {resp.text}")

# -------------------------
# Mapbox provider
# -------------------------
class MapboxProvider(BaseProvider):
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("MAPBOX_TOKEN")
        if not self.token:
            raise RuntimeError("Mapbox token not configured (MAPBOX_TOKEN)")
        self.base = "https://api.mapbox.com/geocoding/v5/mapbox.places"

    async def geocode(self, address: str) -> Tuple[float, float]:
        q = quote_plus(address)
        url = f"{self.base}/{q}.json"
        params = {"access_token": self.token, "limit": 1}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                feats = data.get("features", [])
                if not feats:
                    raise GeocodeError("Mapbox: empty result")
                lon, lat = feats[0]["center"]
                return float(lat), float(lon)
            else:
                raise GeocodeError(f"Mapbox HTTP {resp.status_code}: {resp.text}")

# -------------------------
# Google provider
# -------------------------
class GoogleProvider(BaseProvider):
    def __init__(self, key: Optional[str] = None):
        self.key = key or os.environ.get("GOOGLE_GEOCODING_API_KEY")
        if not self.key:
            raise RuntimeError("Google API key not configured (GOOGLE_GEOCODING_API_KEY)")
        self.base = "https://maps.googleapis.com/maps/api/geocode/json"

    async def geocode(self, address: str) -> Tuple[float, float]:
        params = {"address": address, "key": self.key}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.base, params=params)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                if status == "OK":
                    loc = data["results"][0]["geometry"]["location"]
                    return float(loc["lat"]), float(loc["lng"])
                else:
                    raise GeocodeError(f"Google status: {status}")
            else:
                raise GeocodeError(f"Google HTTP {resp.status_code}: {resp.text}")

# -------------------------
# HERE provider
# -------------------------
class HereProvider(BaseProvider):
    def __init__(self, key: Optional[str] = None):
        self.key = key or os.environ.get("HERE_API_KEY")
        if not self.key:
            raise RuntimeError("HERE API key not configured (HERE_API_KEY)")
        self.base = "https://geocode.search.hereapi.com/v1/geocode"

    async def geocode(self, address: str) -> Tuple[float, float]:
        params = {"q": address, "apiKey": self.key}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.base, params=params)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    raise GeocodeError("HERE: empty result")
                pos = items[0]["position"]
                return float(pos["lat"]), float(pos["lng"])
            else:
                raise GeocodeError(f"HERE HTTP {resp.status_code}: {resp.text}")

# -------------------------
# LocationIQ provider
# -------------------------
class LocationIQProvider(BaseProvider):
    def __init__(self, key: Optional[str] = None):
        self.key = key or os.environ.get("LOCATIONIQ_KEY")
        if not self.key:
            raise RuntimeError("LocationIQ key not configured (LOCATIONIQ_KEY)")
        self.base = "https://us1.locationiq.com/v1/search"

    async def geocode(self, address: str) -> Tuple[float, float]:
        params = {"q": address, "key": self.key, "format": "json", "limit": 1}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.base, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if not data:
                    raise GeocodeError("LocationIQ: empty result")
                return float(data[0]["lat"]), float(data[0]["lon"])
            else:
                raise GeocodeError(f"LocationIQ HTTP {resp.status_code}: {resp.text}")

# -------------------------
# OpenCage provider
# -------------------------
class OpenCageProvider(BaseProvider):
    def __init__(self, key: Optional[str] = None):
        self.key = key or os.environ.get("OPENCAGE_KEY")
        if not self.key:
            raise RuntimeError("OpenCage key not configured (OPENCAGE_KEY)")
        self.base = "https://api.opencagedata.com/geocode/v1/json"

    async def geocode(self, address: str) -> Tuple[float, float]:
        params = {"q": address, "key": self.key, "limit": 1}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.base, params=params)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    raise GeocodeError("OpenCage: empty result")
                geom = results[0]["geometry"]
                return float(geom["lat"]), float(geom["lng"])
            else:
                raise GeocodeError(f"OpenCage HTTP {resp.status_code}: {resp.text}")

# -------------------------
# GeocoderManager: cache + fallback order + logging
# -------------------------
class GeocoderManager:
    def __init__(self, providers, use_cache=True):
        self.providers = providers
        self.use_cache = use_cache

    async def _cache_get(self, address: str):
        return await asyncio.to_thread(_cache_get_sync, address)

    async def _cache_set(self, address: str, lat: float, lon: float, provider: str):
        await asyncio.to_thread(_cache_set_sync, address, lat, lon, provider)

    async def geocode(self, address: str, verbose: bool = False) -> Tuple[float, float, str]:
        # normalized key (minimal)
        key = address.strip()
        if self.use_cache:
            hit = await self._cache_get(key)
            if hit:
                lat, lon, provider = hit
                if verbose:
                    print(f"[geocode] cache hit -> {provider} for '{address}'")
                return lat, lon, provider

        last_exc = None
        for p in self.providers:
            try:
                if verbose:
                    print(f"[geocode] trying provider {p.__class__.__name__}")
                t0 = time.time()
                lat, lon = await p.geocode(address)
                latency = time.time() - t0
                if verbose:
                    print(f"[geocode] {p.__class__.__name__} succeeded in {latency:.2f}s -> {lat},{lon}")
                if self.use_cache:
                    await self._cache_set(key, lat, lon, p.__class__.__name__)
                return lat, lon, p.__class__.__name__
            except Exception as e:
                last_exc = e
                if verbose:
                    print(f"[geocode] {p.__class__.__name__} failed: {e}")
                # try next provider

        raise GeocodeError(f"All providers failed: {last_exc}")

# -------------------------
# Convenience factory
# -------------------------
def default_manager():
    providers = []
    order = os.environ.get(
        "GEOCODER_ORDER", "nominatim,locationiq,opencage,here,mapbox,google"
    ).split(",")
    for name in order:
        name = name.strip().lower()
        try:
            if name == "nominatim":
                providers.append(NominatimProvider())
            elif name == "locationiq":
                providers.append(LocationIQProvider())
            elif name == "opencage":
                providers.append(OpenCageProvider())
            elif name == "here":
                providers.append(HereProvider())
            elif name == "mapbox":
                providers.append(MapboxProvider())
            elif name == "google":
                providers.append(GoogleProvider())
        except Exception as e:
            print(f"[geocode.factory] skipping provider {name}: {e}")
    return GeocoderManager(providers)

