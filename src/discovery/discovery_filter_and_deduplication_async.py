import os
import yaml
import overpy
import asyncio
import httpx
from geopy.distance import geodesic
from src.core.config import settings

# ------------------------------------------------------------------------------
# Optional argument defaults (editable at the top)
# ------------------------------------------------------------------------------
DEFAULT_DEDUPLICATE = True          # Merge duplicate suppliers by proximity & name
DEFAULT_REVERSE_GEOCODE = False     # Fetch human-readable addresses asynchronously

# ------------------------------------------------------------------------------
# Load Overpass filters from YAML
# ------------------------------------------------------------------------------
FILTERS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "industrial_filters.yaml"
)

with open(FILTERS_FILE, "r") as f:
    FILTERS = yaml.safe_load(f).get("overpass_filters", [])

# Overpass API client
api = overpy.Overpass(url=settings.overpass_url)

# ------------------------------------------------------------------------------
# Confidence scoring
# ------------------------------------------------------------------------------
def score_supplier(tags: dict) -> float:
    """Simple keyword-based confidence."""
    name = tags.get("name", "").lower()
    if any(k in name for k in ["aero", "avionics", "composite", "defence", "machining"]):
        return 0.9
    if "industrial" in tags or "building" in tags:
        return 0.7
    return 0.5

# ------------------------------------------------------------------------------
# Deduplication
# ------------------------------------------------------------------------------
def deduplicate_suppliers(suppliers: list[dict], distance_m: float = 50.0) -> list[dict]:
    """Merge suppliers by proximity and name similarity."""
    unique = []
    for s in suppliers:
        for u in unique:
            dist = geodesic((s["lat"], s["lon"]), (u["lat"], u["lon"])).meters
            same_name = s["name"].lower() == u["name"].lower() or "unknown" in (s["name"].lower(), u["name"].lower())
            if dist < distance_m and same_name:
                if s["confidence"] > u["confidence"]:
                    u.update(s)
                break
        else:
            unique.append(s)
    return unique

# ------------------------------------------------------------------------------
# Async reverse geocode
# ------------------------------------------------------------------------------
async def async_reverse_geocode(lat: float, lon: float) -> dict:
    """Return address info from Nominatim asynchronously."""
    url = f"{settings.nominatim_url}/reverse"
    params = {"format": "json", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                addr = resp.json().get("address", {})
                return {
                    "street": addr.get("road", ""),
                    "postcode": addr.get("postcode", ""),
                    "city": addr.get("city", addr.get("town", "")),
                    "country": addr.get("country", "")
                }
        except Exception:
            return {}
    return {}

# ------------------------------------------------------------------------------
# Helper to convert Overpass elements to supplier dict
# ------------------------------------------------------------------------------
def element_to_supplier(element, lat0, lon0) -> dict:
    """Convert a node or way element to a supplier dict."""
    lat, lon = getattr(element, "center_lat", getattr(element, "lat", None)), getattr(element, "center_lon", getattr(element, "lon", None))
    dist = geodesic((lat0, lon0), (lat, lon)).miles
    return {
        "name": element.tags.get("name", "Unknown"),
        "address": element.tags.get("addr:full", ""),
        "lat": lat,
        "lon": lon,
        "distance_miles": round(dist, 2),
        "source": "overpass",
        "confidence": score_supplier(element.tags),
    }

# ------------------------------------------------------------------------------
# Main discovery function
# ------------------------------------------------------------------------------
async def find_suppliers(
    lat: float,
    lon: float,
    radius_miles: float,
    deduplicate: bool = DEFAULT_DEDUPLICATE,
    reverse_geocode: bool = DEFAULT_REVERSE_GEOCODE
) -> list[dict]:
    """
    Fetch aerospace/industrial suppliers from Overpass.

    Arguments:
    - lat, lon: center coordinates
    - radius_miles: search radius in miles
    - deduplicate: merge duplicates based on distance & name (optional, default at top)
    - reverse_geocode: fetch human-readable addresses asynchronously (optional, default at top)
    """
    radius_m = radius_miles * 1609.34

    # Build Overpass query dynamically
    clauses = []
    for f in FILTERS:
        clauses.extend([
            f"node(around:{int(radius_m)},{lat},{lon})[{f}];",
            f"way(around:{int(radius_m)},{lat},{lon})[{f}];"
        ])
    query = f"({''.join(clauses)}); out center;"
    result = api.query(query)

    # Convert all elements to supplier dicts
    suppliers = [element_to_supplier(e, lat, lon) for e in result.nodes + result.ways
                 if getattr(e, 'lat', True) or getattr(e, 'center_lat', True)]

    # Optional async enrichment
    if reverse_geocode and suppliers:
        tasks = [async_reverse_geocode(s["lat"], s["lon"]) for s in suppliers]
        addresses = await asyncio.gather(*tasks)
        for s, a in zip(suppliers, addresses):
            s.update(a)

    # Optional deduplication
    if deduplicate:
        suppliers = deduplicate_suppliers(suppliers)

    # Return sorted by distance
    return sorted(suppliers, key=lambda x: x["distance_miles"])
