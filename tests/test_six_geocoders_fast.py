# tests/test_six_geocoders_fast.py
import pytest
import importlib

# import the module under test
import src.geocode.six_geocoder as six_gc

# --- Helpers: mock provider factories ---
class MockProvider:
    def __init__(self, lat=None, lon=None, fail=False):
        self.lat = lat
        self.lon = lon
        self.fail = fail
        self.calls = 0

    def geocode(self, address: str, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("simulated provider failure")
        return (self.lat, self.lon)

# --- Mock cache object for injection ---
class MockCache:
    def __init__(self):
        self.store = {}
        self.get_calls = 0
        self.set_calls = 0

    def get(self, address):
        self.get_calls += 1
        return self.store.get(address)

    def set(self, address, lat, lon, provider):
        self.set_calls += 1
        self.store[address] = (lat, lon, provider)

@pytest.fixture(autouse=True)
def isolate_module(monkeypatch):
    """
    Ensure the six_geocoder module runs with fresh mocks for each test.
    """
    # reload module to reset module-level state if necessary
    importlib.reload(six_gc)
    # replace _cache with a fresh MockCache
    mc = MockCache()
    monkeypatch.setattr(six_gc, "_cache", mc)
    yield

def test_fallback_order_first_fails_second_succeeds(monkeypatch):
    # Mock the provider modules inside six_gc
    p_fail = MockProvider(fail=True)
    p_ok = MockProvider(lat=51.4545, lon=-2.5879, fail=False)

    # patch the provider modules' geocode functions used by six_gc
    monkeypatch.setattr(six_gc, "nominatim_geocoder", type("M", (), {"geocode": p_fail.geocode}))
    monkeypatch.setattr(six_gc, "mapbox_geocoder", type("M", (), {"geocode": p_ok.geocode}))

    lat, lon = six_gc.geocode("some address", provider_order=["nominatim", "mapbox"], use_cache=False)
    assert (lat, lon) == (p_ok.lat, p_ok.lon)
    assert p_fail.calls == 1
    assert p_ok.calls == 1

def test_cache_prevents_second_call(monkeypatch):
    provider = MockProvider(lat=51.0, lon=-2.0, fail=False)
    # patch only one provider
    monkeypatch.setattr(six_gc, "nominatim_geocoder", type("M", (), {"geocode": provider.geocode}))

    # first call -> provider invoked, cache set
    lat1, lon1 = six_gc.geocode("dup address", provider_order=["nominatim"], use_cache=True)
    # second call -> served from cache, provider shouldn't be called again
    lat2, lon2 = six_gc.geocode("dup address", provider_order=["nominatim"], use_cache=True)

    assert (lat1, lon1) == (lat2, lon2) == (provider.lat, provider.lon)
    assert provider.calls == 1
    # validate mock cache metadata
    assert six_gc._cache.get_calls >= 1
    assert six_gc._cache.set_calls == 1

def test_all_providers_fail_raises(monkeypatch):
    # Make every provider raise
    fail_obj = MockProvider(fail=True)
    # patch all 6 provider modules to the failing provider
    monkeypatch.setattr(six_gc, "nominatim_geocoder", type("M", (), {"geocode": fail_obj.geocode}))
    monkeypatch.setattr(six_gc, "mapbox_geocoder", type("M", (), {"geocode": fail_obj.geocode}))
    monkeypatch.setattr(six_gc, "google_geocoder", type("M", (), {"geocode": fail_obj.geocode}))
    monkeypatch.setattr(six_gc, "here_geocoder", type("M", (), {"geocode": fail_obj.geocode}))
    monkeypatch.setattr(six_gc, "locationiq_geocoder", type("M", (), {"geocode": fail_obj.geocode}))
    monkeypatch.setattr(six_gc, "opencage_geocoder", type("M", (), {"geocode": fail_obj.geocode}))

    with pytest.raises(Exception):
        six_gc.geocode("some address", provider_order=["nominatim","mapbox","google","here","locationiq","opencage"], use_cache=False)

def test_geocode_async_returns_same(monkeypatch):
    # patch a provider and test geocode_async wrapper
    provider = MockProvider(lat=10.0, lon=20.0, fail=False)
    monkeypatch.setattr(six_gc, "nominatim_geocoder", type("M", (), {"geocode": provider.geocode}))
    # call async wrapper
    import asyncio
    lat, lon = asyncio.run(six_gc.geocode_async("address", provider_order=["nominatim"], use_cache=False))
    assert (lat, lon) == (provider.lat, provider.lon)
    assert provider.calls == 1
