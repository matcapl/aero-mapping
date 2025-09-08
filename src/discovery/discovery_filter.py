import os
import yaml
import requests
import overpy
from geopy.distance import geodesic
from src.core.config import settings

# ------------------------------------------------------------------------------
# Config toggles
# ------------------------------------------------------------------------------
# Enable reverse-geocode enrichment? (default: False)
USE_NOMINATIM_REVERSE_GEOCODE = False

# Path to filter configuration
FILTERS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "industrial_filters.yaml"
)

# ------------------------------------------------------------------------------
# Load Overpass filters from YAML
# ------------------------------------------------------------------------------
with open(FILTERS_FILE, "r") as f:
    config = yaml.safe_load(f)
FILTERS = config.get("overpass_filters", [])

# ------------------------------------------------------------------------------
# Overpass API
# ------------------------------------------------------------------------------
api = overpy.Overpass(url=settings.overpass_url)


# ------------------------------------------------------------------------------
# Optional reverse-geocode enrichment
# ------------------------------------------------------------------------------
def reverse_geocode(lat: float, lon: float) -> dict:
    """Lookup address info from Nominatim (if enabled)."""
    url = f"{settings.nominatim_url}/reverse"
    params = {
        "format": "json",
        "lat": lat,
        "lon": lon,
        "zoom": 18,
        "addressdetails": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.ok:
            addr = resp.json().get("address", {})
            return {
                "street": addr.get("road", ""),
                "postcode": addr.get("postcode", ""),
                "city": addr.get("city", addr.get("town", "")),
                "country": addr.get("country", ""),
            }
    except Exception:
        pass
    return {}


# ------------------------------------------------------------------------------
# Confidence scoring heuristic
# ------------------------------------------------------------------------------
def score_supplier(tags: dict) -> float:
    """Assign confidence score based on tags & names."""
    name = tags.get("name", "").lower()
    if any(k in name for k in ["aero", "avionics", "composite", "defence", "machining"]):
        return 0.9
    if "industrial" in tags or "building" in tags:
        return 0.7
    return 0.5


# ------------------------------------------------------------------------------
# Supplier finder
# ------------------------------------------------------------------------------
async def find_suppliers(lat: float, lon: float, radius_miles: float) -> list[dict]:
    """Query Overpass for industrial/aerospace-related suppliers."""
    radius_m = radius_miles * 1609.34

    # Build dynamic Overpass query
    clauses = []
    for f in FILTERS:
        clauses.append(f"node(around:{int(radius_m)},{lat},{lon})[{f}];")
        clauses.append(f"way(around:{int(radius_m)},{lat},{lon})[{f}];")

    query = f"""
    (
      {"".join(clauses)}
    );
    out center;
    """

    result = api.query(query)
    suppliers = []

    # Handle nodes
    for node in result.nodes:
        coord = (node.lat, node.lon)
        dist = geodesic((lat, lon), coord).miles
        supplier = {
            "name": node.tags.get("name", "Unknown"),
            "address": node.tags.get("addr:full", ""),
            "lat": node.lat,
            "lon": node.lon,
            "distance_miles": round(dist, 2),
            "source": "overpass",
            "confidence": score_supplier(node.tags),
        }
        if USE_NOMINATIM_REVERSE_GEOCODE:
            supplier.update(reverse_geocode(node.lat, node.lon))
        suppliers.append(supplier)

    # Handle ways
    for way in result.ways:
        if way.center_lat is None or way.center_lon is None:
            continue
        coord = (way.center_lat, way.center_lon)
        dist = geodesic((lat, lon), coord).miles
        supplier = {
            "name": way.tags.get("name", "Unknown"),
            "address": way.tags.get("addr:full", ""),
            "lat": way.center_lat,
            "lon": way.center_lon,
            "distance_miles": round(dist, 2),
            "source": "overpass",
            "confidence": score_supplier(way.tags),
        }
        if USE_NOMINATIM_REVERSE_GEOCODE:
            supplier.update(reverse_geocode(way.center_lat, way.center_lon))
        suppliers.append(supplier)

    # TODO: implement deduplication (cluster by name + location)

    return sorted(suppliers, key=lambda x: x["distance_miles"])
