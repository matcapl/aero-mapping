# tests/test_three_geocoders.py
import asyncio
import pytest

# Import the GeocoderManager and module-level helpers so we can monkeypatch the cache.
import src.geocode.providers as providers_module
from src.geocode.providers import GeocoderManager

# -------------------------
# Mock providers (async)
# -------------------------
class MockFailProvider:
    """Always fails to simulate provider outage."""
    def __init__(self):
        self.call_count = 0

    async def geocode(self, address: str):
        self.call_count += 1
        raise RuntimeError("simulated failure")


class MockSuccessProvider:
    """Always returns deterministic coordinates."""
    def __init__(self, lat: float, lon: float, name: str = "MockSuccessProvider"):
        self.lat = lat
        self.lon = lon
        self.call_count = 0
        self._name = name

    async def geocode(self, address: str):
        self.call_count += 1
        # small artificial delay to simulate network
        await asyncio.sleep(0.001)
        return self.lat, self.lon

    def __repr__(self):
        return f"<{self._name} lat={self.lat} lon={self.lon} calls={self.call_count}>"

# -------------------------
# Fixtures
# -------------------------
@pytest.fixture(autouse=True)
def ensure_event_loop_policy():
    # ensures event loop is available and uses pytest-asyncio default
    pass

# -------------------------
# Tests
# -------------------------
@pytest.mark.asyncio
async def test_provider_fallback_no_cache():
    """
    If the first provider fails and the second succeeds,
    manager should return the second provider's coordinates
    and both providers should have been called exactly once.
    """
    p1 = MockFailProvider()
    p2 = MockSuccessProvider(51.4545, -2.5879, name="SuccessA")  # Bristol-ish coords

    gm = GeocoderManager([p1, p2], use_cache=False)
    lat, lon, provider_name = await gm.geocode("some address", verbose=False)

    assert (lat, lon) == (p2.lat, p2.lon)
    # ensure both attempted exactly once
    assert p1.call_count == 1
    assert p2.call_count == 1
    assert provider_name.endswith("SuccessA") or "Success" in provider_name

@pytest.mark.asyncio
async def test_cache_prevents_second_call(monkeypatch):
    """
    Ensure caching works: the provider should be called once for the same address,
    second call to gm.geocode returns from cache and provider.call_count remains 1.
    We monkeypatch the sqlite sync cache functions to use an in-memory dict for test isolation.
    """
    # small in-memory dict acting as cache store
    memcache = {}

    def _mock_cache_get_sync(address: str):
        return memcache.get(address)

    def _mock_cache_set_sync(address: str, lat: float, lon: float, provider: str):
        memcache[address] = (lat, lon, provider)

    # inject the mock cache functions
    monkeypatch.setattr(providers_module, "_cache_get_sync", _mock_cache_get_sync)
    monkeypatch.setattr(providers_module, "_cache_set_sync", _mock_cache_set_sync)

    p = MockSuccessProvider(51.0, -2.0, name="CachedProvider")
    gm = GeocoderManager([p], use_cache=True)

    # first call: provider should be invoked
    lat1, lon1, prov1 = await gm.geocode("duplicate address")
    # second call: should be served from cache, provider.call_count still 1
    lat2, lon2, prov2 = await gm.geocode("duplicate address")

    assert (lat1, lon1) == (lat2, lon2) == (p.lat, p.lon)
    assert p.call_count == 1
    assert prov1 == prov2

@pytest.mark.asyncio
async def test_all_providers_fail_raises():
    """If every provider fails the manager should raise a GeocodeError (or RuntimeError)."""
    p1 = MockFailProvider()
    p2 = MockFailProvider()
    gm = GeocoderManager([p1, p2], use_cache=False)

    with pytest.raises(Exception):
        await gm.geocode("whatever address")
