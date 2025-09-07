import os, requests
from urllib.parse import urlencode
from src.core.config import settings

def geocode_address(address: str) -> tuple[float,float]:
    params = {'q': address, 'format': 'json', 'limit':1}
    headers = {'User-Agent': 'aero-mapping/1.0'}
    resp = requests.get(f"{settings.nominatim_url}?{urlencode(params)}", headers=headers)
    data = resp.json()
    if not data:
        raise ValueError("No geocode result")
    return float(data[0]['lat']), float(data[0]['lon'])
