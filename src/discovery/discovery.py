import os, overpy
from geopy.distance import geodesic
from src.core.config import settings

api = overpy.Overpass(url=settings.overpass_url)

async def find_suppliers(lat: float, lon: float, radius_miles: float) -> list[dict]:
    radius_m = radius_miles * 1609.34
    query = f"""
    node(around:{int(radius_m)},{lat},{lon})[industrial~"yes|landuse|zone"];
    out center;
    """
    result = api.query(query)
    suppliers = []
    for node in result.nodes:
        coord = (node.lat, node.lon)
        dist = geodesic((lat, lon), coord).miles
        suppliers.append({
            'name': node.tags.get('name','Unknown'),
            'address': node.tags.get('addr:full',''),
            'lat': node.lat, 'lon': node.lon,
            'distance_miles': round(dist,2),
            'source':'overpass','confidence':0.7
        })
    return sorted(suppliers, key=lambda x: x['distance_miles'])
