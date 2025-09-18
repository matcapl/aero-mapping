# src/geocode/initial_comparison.py
import asyncio
import time
import json
from src.geocode.providers import (
    NominatimProvider, LocationIQProvider, OpenCageProvider,
    HereProvider, MapboxProvider, GoogleProvider, GeocodeError
)

async def compare_all_providers():
    """Compare all six geocoding providers for the same address."""
    
    test_addresses = [
        "Airbus, Filton, Bristol, UK",
        "Rolls-Royce, Derby, UK",
    ]
    
    providers = []
    try:
        providers = [
            ("Nominatim", NominatimProvider()),
            ("LocationIQ", LocationIQProvider()), 
            ("OpenCage", OpenCageProvider()),
            ("HERE", HereProvider()),
            ("Mapbox", MapboxProvider()),
            ("Google", GoogleProvider())
        ]
    except Exception as e:
        print(f"Provider initialization error: {e}")
    
    results = {}
    
    for address in test_addresses:
        print(f"\n=== Testing: {address} ===")
        results[address] = {}
        
        for name, provider in providers:
            try:
                start = time.time()
                lat, lon = await provider.geocode(address)
                duration = time.time() - start
                
                results[address][name] = {
                    "success": True,
                    "lat": lat,
                    "lon": lon, 
                    "duration_ms": round(duration * 1000, 2),
                    "error": None
                }
                print(f"✅ {name:12} | {lat:8.5f}, {lon:9.5f} | {duration*1000:6.1f}ms")
                
                # Respect rate limits
                if name == "Nominatim":
                    await asyncio.sleep(1.1)  # 1s + buffer
                    
            except Exception as e:
                results[address][name] = {
                    "success": False,
                    "lat": None, 
                    "lon": None,
                    "duration_ms": None,
                    "error": str(e)
                }
                print(f"❌ {name:12} | Failed: {str(e)[:50]}...")
    
    # Save detailed results
    with open("provider_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results

if __name__ == "__main__":
    asyncio.run(compare_all_providers())
