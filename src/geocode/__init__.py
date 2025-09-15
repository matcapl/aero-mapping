# src/geocode/__init__.py
from .providers import default_manager
geocoder = default_manager()

# should i use this?
from .six_geocoder import geocode, geocode_async, GeocodingError
__all__ = ["geocode", "geocode_async", "GeocodingError"]

# or this?
async def geocode_async(address):
    return await asyncio.to_thread(geocode_address, address)
