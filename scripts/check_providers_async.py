# scripts/check_providers_async.py
# probably obsolete now
# Your main async pipeline (run_pipeline + CLI) already does all geocoding via default_manager().
# You already log which provider succeeds per address when running run_pipeline.
# The script does not integrate with the DB, CSV export, or your supplier discovery flow — it’s purely standalone.
# Recommendation:
# You can keep it for ad-hoc testing, e.g., to quickly verify that a new API key works.
# But it’s not required for your production pipeline, and nothing in your make test-providers or main CLI uses it.
import asyncio
import os
from src.geocode.providers import default_manager

async def main():
    mgr = default_manager()
    addresses = [
        "1000 Enterprise Way, Bristol BS34 8QZ, UK",
        "10 Downing Street, London, UK",
        "1600 Amphitheatre Parkway, Mountain View, CA"
    ]
    for addr in addresses:
        try:
            lat, lon, provider = await mgr.geocode(addr, verbose=True)
            print(f"OK: [{provider}] {addr} -> {lat:.6f},{lon:.6f}")
        except Exception as e:
            print(f"FAIL for '{addr}': {e}")

if __name__ == "__main__":
    asyncio.run(main())
