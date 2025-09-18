Got it ✅ — sounds like you want a **roadmap-style instruction file** you can keep alongside the codebase, so you (or the team) can enable/disable enrichment later without changing core code every time.

Here’s what I suggest:

---

## 📝 Instruction for Supplier Discovery Improvements

### 1. **Configurable enrichment toggle**

Add a setting near the top of `discovery.py`:

```python
# Config toggle: use reverse geocoding to enrich results with addresses
USE_NOMINATIM_REVERSE_GEOCODE = False  # Set True to enable enrichment
```

When `True`, call Nominatim reverse-geocode for each supplier’s `(lat, lon)` and attach `street`, `postcode`, `city`.
Default stays `False` so we don’t overload Nominatim during testing.

---

### 2. **Move selection logic into YAML**

Instead of hardcoding Overpass filters in Python, define them in `industrial_filters.yaml`:

```yaml
overpass_filters:
  - 'landuse=industrial'
  - 'industrial=manufacture'
  - 'industrial=engineering'
  - 'industrial=electronics'
  - 'industrial=metal'
  - 'industrial=plastic'
  - 'building~"warehouse|industrial|factory"'
  - 'man_made=works'
  - 'craft~"precision|electronics|metal_construction"'
  - 'shop=wholesale'
```

Then `discovery.py` loads these filters dynamically:

```python
import yaml

with open("industrial_filters.yaml") as f:
    config = yaml.safe_load(f)
FILTERS = config["overpass_filters"]
```

This makes it easy to refine supplier definitions later without editing code.

---

### 3. **Address enrichment (optional)**

When `USE_NOMINATIM_REVERSE_GEOCODE=True`, for each supplier:

```python
import requests

def reverse_geocode(lat, lon):
    url = f"{settings.nominatim_url}/reverse"
    params = {"format": "json", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1}
    resp = requests.get(url, params=params)
    if resp.ok:
        addr = resp.json().get("address", {})
        return {
            "street": addr.get("road", ""),
            "postcode": addr.get("postcode", ""),
            "city": addr.get("city", addr.get("town", "")),
            "country": addr.get("country", "")
        }
    return {}
```

Append the result into each supplier dict.

---

### 4. **Confidence scoring**

Introduce a simple function:

```python
def score_supplier(tags: dict) -> float:
    name = tags.get("name", "").lower()
    if any(k in name for k in ["aero", "avionics", "composite", "defence", "machining"]):
        return 0.9
    if "industrial" in tags or "building" in tags:
        return 0.7
    return 0.5
```

This can later be extended to cross-check Companies House / OpenCorporates data.

---

### 5. **Deduplication**

Cluster suppliers by:

* `(lat, lon)` proximity (within \~50m)
* OR same `name`

If duplicates are found, keep the highest-confidence one.

---

### 6. **Radius flexibility**

Keep `radius_miles` param but consider a config in YAML too:

```yaml
search_radius_miles: [5, 10, 25, 50]
```

This allows testing different supplier catchment areas.

---

## ✅ Implementation plan

1. Add `USE_NOMINATIM_REVERSE_GEOCODE` toggle (quick win).
2. Externalize Overpass filters into `industrial_filters.yaml`.
3. Add optional reverse geocode enrichment.
4. Introduce confidence scoring function.
5. Deduplicate overlapping results.
6. Later, enrich with Companies House / OpenCorporates.

---

This way, your codebase stays simple **now**, but you have a clear path to upgrade it step by step.

---

Would you like me to **write a skeleton `industrial_filters.yaml` + updated `discovery.py` stub** (with enrichment toggle + YAML loading), so you can drop them in now but leave enrichment turned off?


--

Perfect — let’s add a **deduplication helper** that merges overlapping results so you don’t get multiple entries for the same site (common in OSM when an industrial area has both a `landuse=industrial` polygon and a `building=factory` node inside).

---

### 📄 Updated `src/discovery/discovery.py` (with deduplication)

```python
import os
import yaml
import requests
import overpy
from geopy.distance import geodesic
from src.core.config import settings

# ------------------------------------------------------------------------------
# Config toggles
# ------------------------------------------------------------------------------
USE_NOMINATIM_REVERSE_GEOCODE = False  # Set True to enable enrichment

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
# Deduplication helper
# ------------------------------------------------------------------------------
def deduplicate_suppliers(suppliers: list[dict], distance_threshold_m: float = 50.0) -> list[dict]:
    """
    Deduplicate suppliers based on proximity and name similarity.

    - If two entries are within distance_threshold_m and names match (or both are 'Unknown'),
      keep only one with higher confidence.
    """
    unique = []
    for supplier in suppliers:
        matched = False
        for u in unique:
            # Check distance
            dist_m = geodesic(
                (supplier["lat"], supplier["lon"]),
                (u["lat"], u["lon"])
            ).meters

            # Check name similarity
            same_name = (
                supplier["name"].lower() == u["name"].lower()
                or supplier["name"] == "Unknown"
                or u["name"] == "Unknown"
            )

            if dist_m < distance_threshold_m and same_name:
                # Merge: keep the higher-confidence one
                if supplier["confidence"] > u["confidence"]:
                    u.update(supplier)
                matched = True
                break
        if not matched:
            unique.append(supplier)
    return unique


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

    # Deduplicate
    deduped = deduplicate_suppliers(suppliers)

    return sorted(deduped, key=lambda x: x["distance_miles"])
```

---

### 🔑 How the deduplication works

* **Clusters** entries within `50m` of each other.
* If names match (or both unknown), merges them.
* Keeps whichever has **higher confidence**.
* Keeps distinct names even if they’re close (so you don’t merge unrelated businesses).

---

With this, your Filton run (`5 miles`) should now drop from **170+** results to a cleaner set, with duplicates (like “industrial estate polygon” + “factory building inside it”) merged.

---

👉 Do you also want me to update the YAML with **aerospace-specific filters only** (manufacture, engineering, precision) so the dataset is leaner by default, or keep the broader industrial scope and leave filtering to confidence scoring?

--
Dockerfile
If multi-stage feels overkill, single-stage quick-fix: Insert COPY --from=ghcr.io/astral-sh/uv:0.4.17 /uv /bin/uv right after FROM, before your RUN apt.
Test: docker-compose exec <container> uv run python -c "import overpy; print(overpy.__version__)" to verify deps.
Why this? Web-scrapes Docker best practices: Caches deps separately, minimizes layers, avoids runtime bloat—scales for your 40 Tier 1s without image obesity.
--
