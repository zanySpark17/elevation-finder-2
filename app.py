
# Production-ready additions for app.py

from pyproj import Transformer
from functools import lru_cache
import requests

SESSION = requests.Session()

@lru_cache(maxsize=5000)
def detect_county(lat, lon):
    """
    Reliable county detection using FCC Census API.
    Falls back to UNKNOWN if unavailable.
    """
    try:
        url = "https://geo.fcc.gov/api/census/block/find"
        params = {
            "latitude": lat,
            "longitude": lon,
            "format": "json"
        }
        r = SESSION.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        county = data.get("County", {}).get("name")
        if county:
            return county.upper().replace(" COUNTY", "").replace(" ", "_")
    except Exception:
        pass

    return "UNKNOWN"


@lru_cache(maxsize=5000)
def get_elevation_usgs(lat, lon):
    """
    Reliable USGS elevation lookup.
    Returns feet.
    """
    try:
        url = (
            "https://epqs.nationalmap.gov/v1/json"
        )
        params = {
            "x": lon,
            "y": lat,
            "units": "Feet",
            "output": "json"
        }

        r = SESSION.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        return data["value"]
    except Exception:
        return None


@lru_cache(maxsize=1000)
def get_transformer(epsg_code):
    return Transformer.from_crs(
        "EPSG:4326",
        f"EPSG:{epsg_code}",
        always_xy=True
    )


def convert_to_county_coords(lat, lon, county_name, county_epsg_dict):
    epsg = county_epsg_dict.get(county_name)

    if epsg is None:
        return None, None, None

    try:
        transformer = get_transformer(epsg)
        x, y = transformer.transform(lon, lat)
        return x, y, epsg
    except Exception:
        return None, None, None
