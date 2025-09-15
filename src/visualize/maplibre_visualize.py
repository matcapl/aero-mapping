# src/visualize/maplibre_visualize.py
"""
Generate a standalone HTML map using MapLibre GL JS and a raster OSM tile source.

Usage:
    from src.visualize.maplibre_visualize import generate_map
    generate_map(suppliers, center=(lat, lon), output_path="out/map.html")

Parameters:
- suppliers: list[dict], each supplier must have keys: 'name', 'lat', 'lon', 'distance_miles', optional 'address'
- center: (lat, lon) tuple for map center (facility location)
- output_path: path to write HTML file
- tile_url: raster tile template (default: OSM tile server). See notes about usage policy.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional

DEFAULT_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_TILE_SUBDOMAINS = ["a", "b", "c"]

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no" />
  <title>Suppliers map</title>
  <link href="https://unpkg.com/maplibre-gl@2.4.0/dist/maplibre-gl.css" rel="stylesheet" />
  <style>
    body {{ margin:0; padding:0; }}
    #map {{ position:absolute; top:0; bottom:0; width:100%; height:100vh; }}
    .marker-facility {{
      background: #2b8cbe;
      border-radius: 50%;
      width: 14px; height: 14px;
      box-shadow: 0 0 0 3px rgba(43,140,190,0.25);
    }}
    .marker-supplier {{
      background: #f03b20;
      border-radius: 50%;
      width: 10px; height: 10px;
      box-shadow: 0 0 0 3px rgba(240,59,32,0.18);
    }}
    .mapboxgl-popup-content {{ font-family: Arial, sans-serif; font-size: 13px; }}
    .attribution {{ position: absolute; bottom: 8px; left: 8px; background: rgba(255,255,255,0.8); padding:6px 8px; border-radius:4px; font-size:12px; }}
  </style>
</head>
<body>
<div id="map"></div>
<div class="attribution">Map tiles: © OpenStreetMap contributors</div>
<script src="https://unpkg.com/maplibre-gl@2.4.0/dist/maplibre-gl.js"></script>
<script>
  // Inline style using raster tiles (suitable for MapLibre)
  const style = {{
    version: 8,
    sources: {{
      "raster-tiles": {{
        type: "raster",
        tiles: {tiles_array},
        tileSize: 256,
        attribution: "© OpenStreetMap contributors"
      }}
    }},
    layers: [
      {{ id: "osm-tiles", type: "raster", source: "raster-tiles", minzoom: 0, maxzoom: 19 }}
    ]
  }};

  const map = new maplibregl.Map({{
    container: "map",
    style: style,
    center: [{center_lon}, {center_lat}],
    zoom: {zoom}
  }});

  // GeoJSON features inserted inline
  const geojson = {geojson};

  map.on('load', () => {{
    // Add suppliers/facility as a GeoJSON source
    map.addSource('points', {{ type: 'geojson', data: geojson }});

    // Circle layer for suppliers
    map.addLayer({{
      id: 'suppliers-layer',
      type: 'circle',
      source: 'points',
      filter: ['==', ['get', 'type'], 'supplier'],
      paint: {{
        'circle-radius': 6,
        'circle-color': '#f03b20',
        'circle-stroke-color': '#fff',
        'circle-stroke-width': 1
      }}
    }});

    // Symbol layer for facility (larger)
    map.addLayer({{
      id: 'facility-layer',
      type: 'circle',
      source: 'points',
      filter: ['==', ['get', 'type'], 'facility'],
      paint: {{
        'circle-radius': 8,
        'circle-color': '#2b8cbe',
        'circle-stroke-color': '#fff',
        'circle-stroke-width': 1.5
      }}
    }});

    // Popup on click
    map.on('click', 'suppliers-layer', (e) => {{
      const props = e.features[0].properties;
      const html = `<strong>${{props.name}}</strong><br/>${{props.address || ''}}<br/>${{props.distance_miles}} miles`;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(html).addTo(map);
    }});
    map.on('click', 'facility-layer', (e) => {{
      const props = e.features[0].properties;
      const html = `<strong>Facility: ${{props.name}}</strong><br/>${{props.address || ''}}`;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(html).addTo(map);
    }});

    // Change the cursor to a pointer when over points
    map.on('mouseenter', 'suppliers-layer', () => map.getCanvas().style.cursor = 'pointer');
    map.on('mouseleave', 'suppliers-layer', () => map.getCanvas().style.cursor = '');
    map.on('mouseenter', 'facility-layer', () => map.getCanvas().style.cursor = 'pointer');
    map.on('mouseleave', 'facility-layer', () => map.getCanvas().style.cursor = '');
  }});
</script>
</body>
</html>
"""

def _build_geojson(suppliers: List[Dict], center: Tuple[float, float], facility_name: str = "Facility") -> Dict:
    # center is (lat, lon)
    features = []
    # facility
    features.append({
        "type": "Feature",
        "properties": {"name": facility_name, "type": "facility", "address": "", "distance_miles": 0},
        "geometry": {"type": "Point", "coordinates": [center[1], center[0]]}
    })
    for s in suppliers:
        # ensure lat/lon exist
        lat = s.get("lat")
        lon = s.get("lon")
        if lat is None or lon is None:
            continue
        props = {
            "name": s.get("name", "Unknown"),
            "address": s.get("address", ""),
            "distance_miles": s.get("distance_miles", "")
        }
        features.append({
            "type": "Feature",
            "properties": {**props, "type": "supplier"},
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}
        })
    return {"type": "FeatureCollection", "features": features}

def generate_map(
    suppliers: List[Dict],
    center: Tuple[float, float],
    facility_name: str = "Facility",
    output_path: str = "map.html",
    tile_url: str = DEFAULT_TILE_URL,
    tile_subdomains: Optional[List[str]] = DEFAULT_TILE_SUBDOMAINS,
    zoom: int = 12
) -> str:
    """
    Write an HTML file with MapLibre map and the supplier points.
    Returns the output_path string.
    """
    # Build tiles array substituting {s} with subdomains
    tiles_array = [tile_url.replace("{s}", sd) for sd in tile_subdomains] if "{s}" in tile_url else [tile_url]
    # JSON-encode JS literals
    tiles_array_js = json.dumps(tiles_array)
    geojson_obj = _build_geojson(suppliers, center, facility_name)
    geojson_js = json.dumps(geojson_obj)
    rendered = _HTML_TEMPLATE.format(
        tiles_array=tiles_array_js,
        center_lon=center[1],
        center_lat=center[0],
        zoom=zoom,
        geojson=geojson_js
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered, encoding="utf-8")
    return str(out)
