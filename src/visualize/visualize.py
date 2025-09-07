import folium, pandas as pd

def export_csv(suppliers, path="suppliers.csv"):
    pd.DataFrame(suppliers).to_csv(path, index=False)
    return path

def generate_map(suppliers, center, path="map.html"):
    m = folium.Map(location=center, zoom_start=10)
    for s in suppliers:
        folium.Marker([s['lat'],s['lon']], popup=f"{s['name']} ({s['distance_miles']}mi)").add_to(m)
    m.save(path)
    return path
