#!/usr/bin/env python3
"""
Improved UK Aerospace Geocoding Provider Analysis
Fixed version with better error handling, dependency management, and uv compatibility.
"""
import asyncio
import time
import json
import os
import sys
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import quote_plus
from dataclasses import dataclass, asdict
from pathlib import Path

# Check for required dependencies
try:
    import httpx
except ImportError:
    print("❌ Missing required dependency: httpx")
    print("Install with: uv add httpx")
    sys.exit(1)

try:
    from geopy.distance import geodesic
except ImportError:
    print("❌ Missing required dependency: geopy")  
    print("Install with: uv add geopy")
    sys.exit(1)

@dataclass
class GeocodeResult:
    """Structured result from geocoding provider."""
    provider: str
    success: bool
    lat: Optional[float] = None
    lon: Optional[float] = None
    duration_ms: float = 0.0
    fields_count: int = 0
    available_fields: List[str] = None
    formatted_address: str = ""
    place_type: str = ""
    confidence: Optional[float] = None
    error: Optional[str] = None
    raw_response: Optional[Dict] = None

    def __post_init__(self):
        if self.available_fields is None:
            self.available_fields = []

class ImprovedGeocodingAnalyzer:
    """Improved geocoding analyzer with better error handling."""

    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.session_timeout = httpx.Timeout(15.0)
        self._nominatim_last_call = 0.0

    def _load_api_keys(self) -> Dict[str, Optional[str]]:
        """Load and validate API keys from environment."""
        keys = {
            "google": os.environ.get("GOOGLE_GEOCODING_API_KEY"),
            "here": os.environ.get("HERE_API_KEY"), 
            "mapbox": os.environ.get("MAPBOX_TOKEN"),
            "locationiq": os.environ.get("LOCATIONIQ_KEY"),
            "opencage": os.environ.get("OPENCAGE_KEY")
        }

        print("🔑 API Key Status:")
        configured_count = 0
        for provider, key in keys.items():
            if key:
                configured_count += 1
                # Basic validation - check key format
                if provider == "google" and not key.startswith("AIza"):
                    print(f"  ⚠️  {provider.title():12} Key format may be invalid")
                elif provider == "mapbox" and not (key.startswith("pk.") or key.startswith("sk.")):
                    print(f"  ⚠️  {provider.title():12} Key format may be invalid")
                else:
                    print(f"  ✅ {provider.title():12} Configured ({key[:8]}...{key[-4:]})")
            else:
                print(f"  ❌ {provider.title():12} Missing (set {provider.upper()}_{'API_KEY' if provider != 'mapbox' else 'TOKEN'})")

        print(f"\n📊 {configured_count}/5 providers configured (Nominatim needs no key)")
        return keys

    async def _rate_limit_nominatim(self) -> None:
        """Ensure 1 second gap between Nominatim requests."""
        now = time.time()
        elapsed = now - self._nominatim_last_call
        if elapsed < 1.1:  # 1 second + buffer
            await asyncio.sleep(1.1 - elapsed)
        self._nominatim_last_call = time.time()

    async def _make_request(self, url: str, params: Dict, headers: Dict = None, max_retries: int = 2) -> Tuple[int, Dict]:
        """Make HTTP request with retry logic."""
        headers = headers or {}

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.session_timeout) as client:
                    response = await client.get(url, params=params, headers=headers)
                    return response.status_code, response.json()
            except httpx.TimeoutException:
                if attempt == max_retries:
                    raise Exception(f"Timeout after {max_retries + 1} attempts")
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
            except Exception as e:
                if attempt == max_retries:
                    raise Exception(f"Network error: {str(e)}")
                await asyncio.sleep(0.5 * (attempt + 1))

    async def test_nominatim(self, address: str) -> GeocodeResult:
        """Test Nominatim with improved error handling."""
        await self._rate_limit_nominatim()

        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
            "countrycodes": "gb"
        }
        headers = {"User-Agent": "aero-mapping/1.0 (aerospace-analysis@example.com)"}

        start_time = time.time()

        try:
            status_code, data = await self._make_request(url, params, headers)
            duration_ms = (time.time() - start_time) * 1000

            if status_code == 200 and data:
                result = data[0]
                confidence = min((result.get("importance", 0.5) * 100), 100)

                return GeocodeResult(
                    provider="Nominatim",
                    success=True,
                    lat=float(result["lat"]),
                    lon=float(result["lon"]),
                    duration_ms=round(duration_ms, 1),
                    fields_count=len(result),
                    available_fields=sorted(result.keys()),
                    formatted_address=result.get("display_name", ""),
                    place_type=result.get("type", ""),
                    confidence=round(confidence, 1),
                    raw_response=result
                )
            else:
                return GeocodeResult(
                    provider="Nominatim",
                    success=False,
                    duration_ms=round(duration_ms, 1),
                    error=f"HTTP {status_code} or no results"
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return GeocodeResult(
                provider="Nominatim",
                success=False,
                duration_ms=round(duration_ms, 1),
                error=str(e)
            )

    async def test_google(self, address: str) -> GeocodeResult:
        """Test Google Geocoding API."""
        if not self.api_keys["google"]:
            return GeocodeResult(
                provider="Google",
                success=False,
                error="API key not configured"
            )

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": self.api_keys["google"],
            "region": "uk",
            "components": "country:GB"
        }

        start_time = time.time()

        try:
            status_code, data = await self._make_request(url, params)
            duration_ms = (time.time() - start_time) * 1000

            if status_code == 200 and data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                geometry = result["geometry"]["location"]

                # Map location_type to confidence
                location_type = result["geometry"].get("location_type", "")
                confidence_map = {"ROOFTOP": 95, "RANGE_INTERPOLATED": 85, "GEOMETRIC_CENTER": 75, "APPROXIMATE": 65}
                confidence = confidence_map.get(location_type, 70)

                return GeocodeResult(
                    provider="Google",
                    success=True,
                    lat=geometry["lat"],
                    lon=geometry["lng"],
                    duration_ms=round(duration_ms, 1),
                    fields_count=len(result),
                    available_fields=sorted(result.keys()),
                    formatted_address=result.get("formatted_address", ""),
                    place_type=", ".join(result.get("types", [])),
                    confidence=confidence,
                    raw_response=result
                )
            else:
                error_msg = data.get("status", "Unknown error") if status_code == 200 else f"HTTP {status_code}"
                return GeocodeResult(
                    provider="Google",
                    success=False,
                    duration_ms=round(duration_ms, 1),
                    error=error_msg
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return GeocodeResult(
                provider="Google",
                success=False,
                duration_ms=round(duration_ms, 1),
                error=str(e)
            )

    # Similar improved methods for other providers...
    # (Truncated for brevity, but would include HERE, Mapbox, LocationIQ, OpenCage)

    async def analyze_address(self, address: str, reference_coords: Optional[Tuple[float, float]] = None) -> Dict:
        """Analyze all providers for a single address."""
        print(f"\n🎯 Testing: {address}")

        # Test available providers
        test_methods = [
            self.test_nominatim,
            self.test_google,
            # Add other provider methods here
        ]

        results = []
        for test_method in test_methods:
            provider_name = test_method.__name__.replace("test_", "").title()
            print(f"  {provider_name:12}...", end="", flush=True)

            result = await test_method(address)
            results.append(result)

            if result.success:
                coords = f"{result.lat:.5f}, {result.lon:.5f}"
                time_str = f"{result.duration_ms:6.1f}ms"
                conf_str = f"{result.confidence:4.0f}%" if result.confidence else "N/A"

                accuracy_str = ""
                if reference_coords and result.lat and result.lon:
                    distance = geodesic(reference_coords, (result.lat, result.lon)).meters
                    accuracy_str = f" ({distance:4.0f}m)"

                print(f" ✅ {coords} | {time_str} | {conf_str}{accuracy_str}")
            else:
                print(f" ❌ {result.error}")

        return {
            "address": address,
            "reference_coords": reference_coords,
            "results": [asdict(r) for r in results],
            "successful_count": sum(1 for r in results if r.success),
            "total_count": len(results)
        }

def create_safe_filename(base: str) -> str:
    """Create safe filename with timestamp."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{base}_{timestamp}"

def save_results_safely(data: Any, base_filename: str, extension: str) -> str:
    """Save results without overwriting existing files."""
    filename = f"{create_safe_filename(base_filename)}.{extension}"

    # Ensure output directory exists
    Path("output").mkdir(exist_ok=True)
    filepath = Path("output") / filename

    if extension == "json":
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
    else:
        with open(filepath, "w") as f:
            f.write(str(data))

    return str(filepath)

async def main():
    """Main analysis workflow."""
    print("🚀 Starting UK Aerospace Geocoding Analysis")
    print("=" * 60)

    # Test cases
    test_cases = [
        {
            "address": "Airbus, Filton, Bristol, UK",
            "reference": (51.5088, -2.5783)
        },
        {
            "address": "Rolls-Royce, Derby, UK",
            "reference": (52.9225, -1.4746)
        }
    ]

    analyzer = ImprovedGeocodingAnalyzer()
    analyses = []

    start_time = time.time()

    for test_case in test_cases:
        analysis = await analyzer.analyze_address(
            test_case["address"],
            test_case["reference"]
        )
        analyses.append(analysis)

    total_time = time.time() - start_time

    # Save results
    try:
        results_file = save_results_safely(analyses, "uk_geocoding_results", "json")
        print(f"\n💾 Results saved: {results_file}")

        # Simple report
        report = f"""
Analysis completed in {total_time:.1f} seconds
Addresses tested: {len(analyses)}
Total API calls: {sum(a['total_count'] for a in analyses)}
Successful calls: {sum(a['successful_count'] for a in analyses)}
"""

        report_file = save_results_safely(report, "uk_geocoding_report", "txt")
        print(f"📋 Report saved: {report_file}")

    except Exception as e:
        print(f"⚠️  Error saving results: {e}")

    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    print("UK Aerospace Geocoding Provider Analysis")
    print("Requires: httpx, geopy")
    print()

    asyncio.run(main())