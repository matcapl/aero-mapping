#!/usr/bin/env python3
"""
Comprehensive Geocoding Provider Analysis
Compares all six providers with detailed field analysis and accuracy metrics.
Optimized for UK aerospace locations.
"""
import asyncio
import time
import json
import pandas as pd
import httpx
from typing import Dict, Any, Optional
from urllib.parse import quote_plus
import os
from geopy.distance import geodesic

class UKAerospaceGeocodingAnalyzer:
    """Analyzes geocoding providers for UK aerospace facilities."""
    
    def __init__(self):
        self.api_keys = self._load_api_keys()
        self.results = {}
        
    def _load_api_keys(self):
        """Load API keys from environment variables."""
        keys = {
            "google": os.environ.get("GOOGLE_GEOCODING_API_KEY"),
            "here": os.environ.get("HERE_API_KEY"), 
            "mapbox": os.environ.get("MAPBOX_TOKEN"),
            "locationiq": os.environ.get("LOCATIONIQ_KEY"),
            "opencage": os.environ.get("OPENCAGE_KEY")
        }
        
        print("API Key Status:")
        for provider, key in keys.items():
            status = "✅ Configured" if key else "❌ Missing"
            key_preview = f" ({key[:10]}...)" if key else ""
            print(f"  {provider.title():12} {status}{key_preview}")
        
        return keys
    
    async def test_nominatim(self, address: str) -> Dict:
        """Test Nominatim with detailed response capture."""
        base_url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": address,
            "format": "json", 
            "limit": 1,
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
            "bounded": 1,
            "countrycodes": "gb"  # UK only
        }
        headers = {"User-Agent": "aero-mapping/1.0 (aerospace-analysis@example.com)"}
        
        start_time = time.time()
        
        try:
            # Respect 1 req/sec rate limit
            await asyncio.sleep(1.1)
            
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params, headers=headers)
                duration_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        result = data[0]
                        return {
                            "provider": "Nominatim",
                            "success": True,
                            "lat": float(result["lat"]),
                            "lon": float(result["lon"]),
                            "duration_ms": round(duration_ms, 1),
                            "fields_count": len(result.keys()),
                            "available_fields": sorted(result.keys()),
                            "formatted_address": result.get("display_name", ""),
                            "place_type": result.get("type", ""),
                            "importance": result.get("importance", 0),
                            "confidence": result.get("importance", 0) * 100 if result.get("importance") else None,
                            "raw_response": result,
                            "error": None
                        }
                    else:
                        return {"provider": "Nominatim", "success": False, "error": "No results found", "duration_ms": round(duration_ms, 1)}
                else:
                    return {"provider": "Nominatim", "success": False, "error": f"HTTP {resp.status_code}: {resp.text[:100]}", "duration_ms": round(duration_ms, 1)}
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {"provider": "Nominatim", "success": False, "error": str(e), "duration_ms": round(duration_ms, 1)}
    
    async def test_google(self, address: str) -> Dict:
        """Test Google Geocoding API with detailed response capture."""
        if not self.api_keys["google"]:
            return {"provider": "Google", "success": False, "error": "API key not configured"}
            
        base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": self.api_keys["google"],
            "region": "uk",
            "components": "country:GB"
        }
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                duration_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("results"):
                        result = data["results"][0]
                        geometry = result["geometry"]["location"]
                        
                        # Extract confidence from location_type
                        location_type = result["geometry"].get("location_type", "")
                        confidence_map = {
                            "ROOFTOP": 95,
                            "RANGE_INTERPOLATED": 85,
                            "GEOMETRIC_CENTER": 75,
                            "APPROXIMATE": 65
                        }
                        confidence = confidence_map.get(location_type, 70)
                        
                        return {
                            "provider": "Google",
                            "success": True,
                            "lat": geometry["lat"],
                            "lon": geometry["lng"],
                            "duration_ms": round(duration_ms, 1),
                            "fields_count": len(result.keys()),
                            "available_fields": sorted(result.keys()),
                            "formatted_address": result.get("formatted_address", ""),
                            "place_type": ", ".join(result.get("types", [])),
                            "confidence": confidence,
                            "location_type": location_type,
                            "address_components_count": len(result.get("address_components", [])),
                            "raw_response": result,
                            "error": None
                        }
                    else:
                        return {"provider": "Google", "success": False, "error": f"Status: {data.get('status', 'Unknown')}", "duration_ms": round(duration_ms, 1)}
                else:
                    return {"provider": "Google", "success": False, "error": f"HTTP {resp.status_code}", "duration_ms": round(duration_ms, 1)}
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {"provider": "Google", "success": False, "error": str(e), "duration_ms": round(duration_ms, 1)}
    
    async def test_here(self, address: str) -> Dict:
        """Test HERE Geocoding API with detailed response capture."""
        if not self.api_keys["here"]:
            return {"provider": "HERE", "success": False, "error": "API key not configured"}
            
        base_url = "https://geocode.search.hereapi.com/v1/geocode"
        params = {
            "q": address,
            "apiKey": self.api_keys["here"],
            "in": "countryCode:GBR",
            "limit": 1
        }
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                duration_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("items"):
                        result = data["items"][0]
                        position = result["position"]
                        
                        # Extract confidence from scoring
                        scoring = result.get("scoring", {})
                        confidence = scoring.get("queryScore", 0.5) * 100
                        
                        return {
                            "provider": "HERE",
                            "success": True,
                            "lat": position["lat"],
                            "lon": position["lng"],
                            "duration_ms": round(duration_ms, 1),
                            "fields_count": len(result.keys()),
                            "available_fields": sorted(result.keys()),
                            "formatted_address": result.get("title", "") + ", " + result.get("address", {}).get("label", ""),
                            "place_type": result.get("resultType", ""),
                            "confidence": round(confidence, 1),
                            "query_score": scoring.get("queryScore", 0),
                            "field_score": scoring.get("fieldScore", {}),
                            "raw_response": result,
                            "error": None
                        }
                    else:
                        return {"provider": "HERE", "success": False, "error": "No results found", "duration_ms": round(duration_ms, 1)}
                else:
                    return {"provider": "HERE", "success": False, "error": f"HTTP {resp.status_code}", "duration_ms": round(duration_ms, 1)}
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {"provider": "HERE", "success": False, "error": str(e), "duration_ms": round(duration_ms, 1)}
    
    async def test_mapbox(self, address: str) -> Dict:
        """Test Mapbox Geocoding API with detailed response capture."""
        if not self.api_keys["mapbox"]:
            return {"provider": "Mapbox", "success": False, "error": "API key not configured"}
            
        encoded_address = quote_plus(address)
        base_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_address}.json"
        params = {
            "access_token": self.api_keys["mapbox"],
            "country": "gb",
            "limit": 1
        }
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                duration_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("features"):
                        result = data["features"][0]
                        coordinates = result["center"]
                        
                        # Mapbox relevance as confidence
                        confidence = result.get("relevance", 0.5) * 100
                        
                        return {
                            "provider": "Mapbox",
                            "success": True,
                            "lat": coordinates[1],  # Mapbox returns [lon, lat]
                            "lon": coordinates[0],
                            "duration_ms": round(duration_ms, 1),
                            "fields_count": len(result.keys()),
                            "available_fields": sorted(result.keys()),
                            "formatted_address": result.get("place_name", ""),
                            "place_type": ", ".join(result.get("place_type", [])),
                            "confidence": round(confidence, 1),
                            "relevance": result.get("relevance", 0),
                            "context_count": len(result.get("context", [])),
                            "raw_response": result,
                            "error": None
                        }
                    else:
                        return {"provider": "Mapbox", "success": False, "error": "No results found", "duration_ms": round(duration_ms, 1)}
                else:
                    return {"provider": "Mapbox", "success": False, "error": f"HTTP {resp.status_code}", "duration_ms": round(duration_ms, 1)}
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {"provider": "Mapbox", "success": False, "error": str(e), "duration_ms": round(duration_ms, 1)}
    
    async def test_locationiq(self, address: str) -> Dict:
        """Test LocationIQ API with detailed response capture."""
        if not self.api_keys["locationiq"]:
            return {"provider": "LocationIQ", "success": False, "error": "API key not configured"}
            
        base_url = "https://us1.locationiq.com/v1/search"
        params = {
            "q": address,
            "key": self.api_keys["locationiq"],
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "extratags": 1,
            "countrycodes": "gb"
        }
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                duration_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        result = data[0]
                        
                        # LocationIQ importance as confidence
                        importance = float(result.get("importance", 0.5))
                        confidence = min(importance * 100, 100)
                        
                        return {
                            "provider": "LocationIQ",
                            "success": True,
                            "lat": float(result["lat"]),
                            "lon": float(result["lon"]),
                            "duration_ms": round(duration_ms, 1),
                            "fields_count": len(result.keys()),
                            "available_fields": sorted(result.keys()),
                            "formatted_address": result.get("display_name", ""),
                            "place_type": result.get("type", ""),
                            "confidence": round(confidence, 1),
                            "importance": importance,
                            "osm_type": result.get("osm_type", ""),
                            "raw_response": result,
                            "error": None
                        }
                    else:
                        return {"provider": "LocationIQ", "success": False, "error": "No results found", "duration_ms": round(duration_ms, 1)}
                else:
                    return {"provider": "LocationIQ", "success": False, "error": f"HTTP {resp.status_code}", "duration_ms": round(duration_ms, 1)}
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {"provider": "LocationIQ", "success": False, "error": str(e), "duration_ms": round(duration_ms, 1)}
    
    async def test_opencage(self, address: str) -> Dict:
        """Test OpenCage Geocoding API with detailed response capture."""
        if not self.api_keys["opencage"]:
            return {"provider": "OpenCage", "success": False, "error": "API key not configured"}
            
        base_url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            "q": address,
            "key": self.api_keys["opencage"],
            "limit": 1,
            "countrycode": "gb",
            "no_annotations": 0
        }
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                duration_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("results"):
                        result = data["results"][0]
                        geometry = result["geometry"]
                        
                        # OpenCage confidence
                        confidence = result.get("confidence", 5) * 10  # Scale 1-10 to 10-100
                        
                        return {
                            "provider": "OpenCage",
                            "success": True,
                            "lat": geometry["lat"],
                            "lon": geometry["lng"],
                            "duration_ms": round(duration_ms, 1),
                            "fields_count": len(result.keys()),
                            "available_fields": sorted(result.keys()),
                            "formatted_address": result.get("formatted", ""),
                            "place_type": result.get("components", {}).get("_type", ""),
                            "confidence": round(confidence, 1),
                            "opencage_confidence": result.get("confidence", 0),
                            "components_count": len(result.get("components", {})),
                            "raw_response": result,
                            "error": None
                        }
                    else:
                        return {"provider": "OpenCage", "success": False, "error": "No results found", "duration_ms": round(duration_ms, 1)}
                else:
                    return {"provider": "OpenCage", "success": False, "error": f"HTTP {resp.status_code}", "duration_ms": round(duration_ms, 1)}
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return {"provider": "OpenCage", "success": False, "error": str(e), "duration_ms": round(duration_ms, 1)}
    
    async def analyze_address(self, address: str, reference_coords: tuple = None) -> Dict:
        """Analyze all providers for a single address."""
        print(f"\n🔍 Analyzing: {address}")
        
        # Test all providers
        providers = [
            ("Nominatim", self.test_nominatim),
            ("Google", self.test_google),
            ("HERE", self.test_here),
            ("Mapbox", self.test_mapbox),
            ("LocationIQ", self.test_locationiq),
            ("OpenCage", self.test_opencage)
        ]
        
        results = []
        
        for name, test_func in providers:
            print(f"  Testing {name:12}...", end="", flush=True)
            
            result = await test_func(address)
            results.append(result)
            
            if result["success"]:
                coords_str = f"{result['lat']:.5f}, {result['lon']:.5f}"
                duration_str = f"{result['duration_ms']:6.1f}ms"
                confidence_str = f"{result.get('confidence', 0):4.0f}%" if result.get('confidence') else "  N/A"
                
                # Calculate accuracy if reference provided
                accuracy_str = ""
                if reference_coords and result.get('lat') and result.get('lon'):
                    distance_m = geodesic(reference_coords, (result['lat'], result['lon'])).meters
                    accuracy_str = f" ({distance_m:4.0f}m)"
                
                print(f" ✅ {coords_str} | {duration_str} | {confidence_str}{accuracy_str}")
            else:
                error_preview = result["error"][:40] + "..." if len(result["error"]) > 40 else result["error"]
                print(f" ❌ {error_preview}")
        
        # Calculate statistics
        successful_results = [r for r in results if r["success"]]
        
        analysis = {
            "address": address,
            "reference_coords": reference_coords,
            "total_providers": len(results),
            "successful_providers": len(successful_results),
            "success_rate": len(successful_results) / len(results) * 100,
            "results": results
        }
        
        if successful_results:
            # Find fastest and most accurate
            fastest = min(successful_results, key=lambda x: x["duration_ms"])
            analysis["fastest_provider"] = fastest["provider"]
            analysis["fastest_time"] = fastest["duration_ms"]
            
            # Calculate coordinate variance
            lats = [r["lat"] for r in successful_results]
            lons = [r["lon"] for r in successful_results]
            
            if len(lats) > 1:
                max_distance = max([
                    geodesic((lats[i], lons[i]), (lats[j], lons[j])).meters
                    for i in range(len(lats))
                    for j in range(i+1, len(lats))
                ])
                analysis["coordinate_variance_meters"] = round(max_distance, 1)
            
            # Find most accurate if reference provided
            if reference_coords:
                accuracies = []
                for r in successful_results:
                    distance = geodesic(reference_coords, (r["lat"], r["lon"])).meters
                    accuracies.append((r["provider"], distance))
                
                most_accurate = min(accuracies, key=lambda x: x[1])
                analysis["most_accurate_provider"] = most_accurate[0]
                analysis["best_accuracy_meters"] = round(most_accurate[1], 1)
        
        return analysis

def create_comprehensive_report(analyses: list) -> str:
    """Generate comprehensive comparison report."""
    
    # Collect all results for analysis
    all_results = []
    for analysis in analyses:
        all_results.extend(analysis["results"])
    
    successful_results = [r for r in all_results if r["success"]]
    
    report = f"""
# UK Aerospace Geocoding Provider Analysis
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- Addresses tested: {len(analyses)}
- Providers tested: 6 (Nominatim, Google, HERE, Mapbox, LocationIQ, OpenCage)
- Overall success rate: {len(successful_results)/len(all_results)*100:.1f}%
- Total API calls made: {len(all_results)}

"""
    
    # Performance Summary Table
    provider_stats = {}
    for result in all_results:
        provider = result["provider"]
        if provider not in provider_stats:
            provider_stats[provider] = {
                "total": 0, "successful": 0, "total_time": 0, "successful_time": 0,
                "errors": [], "field_counts": [], "confidences": []
            }
        
        stats = provider_stats[provider]
        stats["total"] += 1
        if result["success"]:
            stats["successful"] += 1
            stats["successful_time"] += result["duration_ms"]
            if "fields_count" in result:
                stats["field_counts"].append(result["fields_count"])
            if result.get("confidence"):
                stats["confidences"].append(result["confidence"])
        else:
            stats["errors"].append(result["error"])
    
    report += "## Provider Performance Summary\n\n"
    report += "| Provider   | Success Rate | Avg Time (ms) | Avg Fields | Avg Confidence | Status |\n"
    report += "|------------|--------------|---------------|------------|----------------|--------|\n"
    
    for provider, stats in provider_stats.items():
        success_rate = (stats["successful"] / stats["total"]) * 100
        avg_time = stats["successful_time"] / max(stats["successful"], 1)
        avg_fields = sum(stats["field_counts"]) / max(len(stats["field_counts"]), 1)
        avg_confidence = sum(stats["confidences"]) / max(len(stats["confidences"]), 1)
        
        status = "✅ Working" if stats["successful"] > 0 else "❌ Failed"
        
        report += f"| {provider:10} | {success_rate:8.1f}% | {avg_time:9.1f} | {avg_fields:8.1f} | {avg_confidence:10.1f}% | {status} |\n"
    
    # Detailed Results by Address
    for analysis in analyses:
        address = analysis["address"]
        report += f"\n## Detailed Results: {address}\n\n"
        
        if analysis.get("reference_coords"):
            ref_lat, ref_lon = analysis["reference_coords"]
            report += f"**Reference coordinates:** {ref_lat:.5f}, {ref_lon:.5f}\n\n"
        
        report += "| Provider   | Success | Coordinates | Accuracy | Time (ms) | Confidence | Error |\n"
        report += "|------------|---------|-------------|----------|-----------|------------|-------|\n"
        
        for result in analysis["results"]:
            if result["success"]:
                coords = f"{result['lat']:.5f}, {result['lon']:.5f}"
                
                accuracy = "N/A"
                if analysis.get("reference_coords"):
                    dist = geodesic(analysis["reference_coords"], (result['lat'], result['lon'])).meters
                    accuracy = f"{dist:.1f}m"
                
                confidence = f"{result.get('confidence', 0):.0f}%" if result.get('confidence') else "N/A"
                
                report += f"| {result['provider']:10} | ✅      | {coords} | {accuracy:8} | {result['duration_ms']:7.1f} | {confidence:8} | - |\n"
            else:
                error_short = result["error"][:30] + "..." if len(result["error"]) > 30 else result["error"]
                report += f"| {result['provider']:10} | ❌      | N/A | N/A | {result.get('duration_ms', 0):7.1f} | N/A | {error_short} |\n"
        
        # Analysis summary for this address
        if analysis["successful_providers"] > 0:
            report += f"\n**Summary for {address}:**\n"
            report += f"- Success rate: {analysis['success_rate']:.1f}%\n"
            report += f"- Fastest provider: {analysis.get('fastest_provider', 'N/A')} ({analysis.get('fastest_time', 0):.1f}ms)\n"
            
            if analysis.get('coordinate_variance_meters'):
                report += f"- Coordinate variance: {analysis['coordinate_variance_meters']}m between providers\n"
            
            if analysis.get('most_accurate_provider'):
                report += f"- Most accurate: {analysis['most_accurate_provider']} ({analysis.get('best_accuracy_meters', 0):.1f}m from reference)\n"
    
    # Field Analysis
    report += "\n## Field Availability Analysis\n\n"
    
    # Collect unique fields from successful results
    all_fields = set()
    provider_fields = {}
    
    for result in successful_results:
        if "available_fields" in result:
            fields = set(result["available_fields"])
            all_fields.update(fields)
            
            provider = result["provider"]
            if provider not in provider_fields:
                provider_fields[provider] = set()
            provider_fields[provider].update(fields)
    
    # Create field matrix
    if all_fields and provider_fields:
        report += "### Key Field Availability\n\n"
        
        important_fields = [
            "lat", "lon", "formatted_address", "display_name", "place_name", 
            "address_components", "geometry", "confidence", "importance",
            "types", "place_type", "components", "context"
        ]
        
        available_important = [f for f in important_fields if f in all_fields]
        
        if available_important:
            report += "| Field | " + " | ".join(sorted(provider_fields.keys())) + " |\n"
            report += "|-------|" + "|".join(["-----"] * len(provider_fields)) + "|\n"
            
            for field in available_important:
                row = f"| {field:20} |"
                for provider in sorted(provider_fields.keys()):
                    has_field = "✅" if field in provider_fields[provider] else "❌"
                    row += f" {has_field:3} |"
                report += row + "\n"
    
    # Recommendations
    report += "\n## Recommendations\n\n"
    
    working_providers = [p for p, s in provider_stats.items() if s["successful"] > 0]
    
    if working_providers:
        # Find best performers
        best_accuracy = None
        fastest = None
        most_reliable = None
        
        for provider in working_providers:
            stats = provider_stats[provider]
            success_rate = stats["successful"] / stats["total"]
            avg_time = stats["successful_time"] / max(stats["successful"], 1)
            
            if success_rate == 1.0:  # 100% success
                if not most_reliable or avg_time < provider_stats[most_reliable]["successful_time"] / provider_stats[most_reliable]["successful"]:
                    most_reliable = provider
            
            if not fastest or avg_time < provider_stats[fastest]["successful_time"] / provider_stats[fastest]["successful"]:
                fastest = provider
        
        report += "### For UK Aerospace Applications:\n\n"
        
        if most_reliable:
            report += f"**Primary choice:** {most_reliable} (100% success rate, reliable for production)\n"
        
        if fastest and fastest != most_reliable:
            report += f"**Speed optimized:** {fastest} (fastest response times)\n"
        
        report += f"**Free option:** Nominatim (no API key required, but rate limited)\n"
        
        report += "\n### Cost Analysis for 20-mile radius:\n"
        report += "- **Google:** $0 (within 10K/month free tier)\n"
        report += "- **HERE:** $0 (within 250/day free tier)\n"
        report += "- **Mapbox:** $0 (within 100K/month free tier)\n"
        report += "- **LocationIQ:** $0 (within 5K/day free tier)\n"
        report += "- **OpenCage:** $0 (within 2.5K/day free tier)\n"
        report += "- **Nominatim:** Free (but respect 1 req/sec limit)\n"
        
        report += f"\n**Estimated cost for 60-mile radius:** $0-25 (well within all free tiers)\n"
    
    else:
        report += "⚠️  No providers are currently working. Check your API keys and configuration.\n"
    
    return report

async def main():
    """Main analysis workflow for UK aerospace facilities."""
    
    # UK Aerospace test cases with known reference coordinates
    test_cases = [
        {
            "address": "Airbus, Filton, Bristol, UK",
            "reference": (51.5088, -2.5783)  # Known Airbus Filton coordinates
        },
        {
            "address": "Rolls-Royce, Derby, UK", 
            "reference": (52.9225, -1.4746)  # Known Rolls-Royce Derby coordinates
        }
    ]
    
    analyzer = UKAerospaceGeocodingAnalyzer()
    analyses = []
    
    print("=" * 80)
    print("UK AEROSPACE GEOCODING PROVIDER ANALYSIS")
    print("=" * 80)
    
    total_start_time = time.time()
    
    for test_case in test_cases:
        analysis = await analyzer.analyze_address(
            test_case["address"],
            test_case["reference"]
        )
        analyses.append(analysis)
    
    total_duration = time.time() - total_start_time
    
    print(f"\n⏱️  Total analysis time: {total_duration:.1f} seconds")
    
    # Generate comprehensive report
    report = create_comprehensive_report(analyses)
    
    # Save results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    results_file = f"uk_aerospace_geocoding_results_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump(analyses, f, indent=2, default=str)
    
    report_file = f"uk_aerospace_geocoding_report_{timestamp}.txt"
    with open(report_file, "w") as f:
        f.write(report)
    
    print(f"\n📊 Results saved to: {results_file}")
    print(f"📋 Report saved to: {report_file}")
    
    # Display report
    print("\n" + "=" * 80)
    print("ANALYSIS REPORT")
    print("=" * 80)
    print(report)

if __name__ == "__main__":
    print("Starting UK Aerospace Geocoding Provider Analysis...")
    print("Ensure your API keys are set in environment variables:")
    print("- GOOGLE_GEOCODING_API_KEY")  
    print("- HERE_API_KEY")
    print("- MAPBOX_TOKEN")
    print("- LOCATIONIQ_KEY") 
    print("- OPENCAGE_KEY")
    print()
    
    asyncio.run(main())