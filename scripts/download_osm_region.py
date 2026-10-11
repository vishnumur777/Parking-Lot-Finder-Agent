"""
Offline OpenStreetMap Region Downloader
Downloads real-world OSM parking spots for any searched city, town, or bounding box
and saves them directly into the offline SQLite database for 100% offline usage.
"""

import os
import sys
import json
import httpx
from typing import Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.import_osm import parse_overpass_json
from osm_database import OsmParkingDatabase

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Bounding box presets for quick download
CITY_BBOXES = {
    "chennai": (12.90, 80.10, 13.20, 80.35),
    "thiruvallur": (13.10, 79.85, 13.20, 80.00),
    "redhills": (13.14, 80.13, 13.25, 80.24),
    "gummidipoondi": (13.35, 80.05, 13.48, 80.20),
    "bangalore": (12.85, 77.45, 13.15, 77.75),
    "mumbai": (18.90, 72.75, 19.30, 73.00),
    "delhi": (28.40, 76.90, 28.85, 77.40),
    "newyork": (40.65, -74.05, 40.85, -73.85),
    "london": (51.40, -0.25, 51.60, 0.05),
}

def search_and_geocode_location(query: str) -> Dict[str, Any]:
    """
    Geocodes any location name (city, town, landmark) via Nominatim OpenStreetMap API.
    Returns location metadata and bounding box.
    """
    cleaned = query.strip()
    if not cleaned:
        return {"found": False, "message": "Search query cannot be empty"}

    # Check local presets first
    preset_key = cleaned.lower().replace(" ", "").replace("-", "")
    for key, bbox in CITY_BBOXES.items():
        if key in preset_key or preset_key in key:
            lat = (bbox[0] + bbox[2]) / 2.0
            lon = (bbox[1] + bbox[3]) / 2.0
            return {
                "found": True,
                "display_name": f"{key.capitalize()}, India",
                "short_name": key.capitalize(),
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "bbox": {
                    "south": bbox[0],
                    "west": bbox[1],
                    "north": bbox[2],
                    "east": bbox[3]
                }
            }

    # Query Nominatim API
    headers = {"User-Agent": "ParkVoiceOfflinePWA/1.0 (https://github.com/osm-offline-pwa)"}
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": cleaned,
        "format": "json",
        "addressdetails": 1,
        "limit": 1
    }

    try:
        with httpx.Client(timeout=10.0, headers=headers) as client:
            resp = client.get(url, params=params)
            if resp.status_code != 200:
                return {"found": False, "message": f"Geocoding service returned HTTP {resp.status_code}"}
            
            data = resp.json()
            if not data or len(data) == 0:
                return {"found": False, "message": f"Location '{cleaned}' not found in OpenStreetMap"}

            item = data[0]
            lat = float(item["lat"])
            lon = float(item["lon"])
            raw_bbox = item.get("boundingbox", [])

            if len(raw_bbox) == 4:
                south = float(raw_bbox[0])
                north = float(raw_bbox[1])
                west = float(raw_bbox[2])
                east = float(raw_bbox[3])
            else:
                south, north = lat - 0.04, lat + 0.04
                west, east = lon - 0.04, lon + 0.04

            # Ensure bounding box is appropriate size (not a point, and not a massive state)
            lat_span = north - south
            lon_span = east - west
            if lat_span < 0.03:
                south = lat - 0.025
                north = lat + 0.025
            elif lat_span > 0.4:
                south = lat - 0.12
                north = lat + 0.12

            if lon_span < 0.03:
                west = lon - 0.025
                east = lon + 0.025
            elif lon_span > 0.4:
                west = lon - 0.12
                east = lon + 0.12

            short_name = (
                item.get("address", {}).get("city")
                or item.get("address", {}).get("town")
                or item.get("address", {}).get("village")
                or item.get("address", {}).get("suburb")
                or item.get("name")
                or cleaned
            )

            return {
                "found": True,
                "display_name": item.get("display_name", cleaned),
                "short_name": short_name,
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "bbox": {
                    "south": round(south, 5),
                    "west": round(west, 5),
                    "north": round(north, 5),
                    "east": round(east, 5)
                }
            }
    except Exception as e:
        print(f"[search_and_geocode_location error]: {e}")
        return {"found": False, "message": f"Geocoding error: {str(e)}"}

def download_parking_by_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    city_name: str = ""
) -> Dict[str, Any]:
    """
    Downloads parking nodes and ways from OpenStreetMap via Overpass API mirrors
    and indexes them in the local offline database.
    Returns: {"success": bool, "count": int, "mirror": str, "message": str}
    """
    query = f"""
    [out:json][timeout:35];
    (
      node["amenity"="parking"]({south},{west},{north},{east});
      way["amenity"="parking"]({south},{west},{north},{east});
    );
    out center tags;
    """
    print(f"Fetching OpenStreetMap data for bbox ({south}, {west}, {north}, {east})...")
    headers = {"User-Agent": "ParkVoiceOfflinePWA/1.0 (https://github.com/osm-offline-pwa)"}

    any_mirror_succeeded = False

    for mirror in OVERPASS_MIRRORS:
        try:
            print(f"Querying Overpass mirror: {mirror}")
            with httpx.Client(timeout=40.0, headers=headers) as client:
                resp = client.post(mirror, data={"data": query})
                if resp.status_code == 200:
                    any_mirror_succeeded = True
                    data = resp.json()
                    spots = parse_overpass_json(data, default_city=city_name)
                    if spots and len(spots) > 0:
                        db = OsmParkingDatabase()
                        count = db.bulk_add_parking_spots(spots)
                        print(f"Successfully downloaded and stored {count} parking spots from {mirror}!")
                        return {
                            "success": True,
                            "count": count,
                            "mirror": mirror,
                            "message": f"Successfully downloaded and stored {count} parking spots from mirror."
                        }
                    else:
                        print(f"Mirror {mirror} succeeded with 0 parking spots in this bbox.")
                        return {
                            "success": True,
                            "count": 0,
                            "mirror": mirror,
                            "message": "No parking spots found in mirrors for this location."
                        }
                else:
                    print(f"Mirror {mirror} returned HTTP {resp.status_code}, trying next mirror...")
        except Exception as e:
            print(f"Mirror {mirror} error: {e}")

    # If all mirrors timed out or failed
    return {
        "success": False,
        "count": 0,
        "mirror": None,
        "message": "No map was found in mirrors (all Overpass mirrors were unreachable or timed out)."
    }

def download_region_by_name(name_or_query: str) -> Dict[str, Any]:
    """
    Resolves any city/location query, fetches bounding box, and downloads OSM data.
    """
    geo = search_and_geocode_location(name_or_query)
    if not geo.get("found"):
        return {
            "success": False,
            "count": 0,
            "city": name_or_query,
            "message": geo.get("message", "Location not found in OpenStreetMap")
        }

    bbox = geo["bbox"]
    city_name = geo.get("short_name", name_or_query)
    res = download_parking_by_bbox(
        bbox["south"], bbox["west"], bbox["north"], bbox["east"],
        city_name=city_name
    )

    res["city"] = city_name
    res["display_name"] = geo.get("display_name", city_name)
    res["latitude"] = geo.get("latitude")
    res["longitude"] = geo.get("longitude")
    res["bbox"] = bbox
    return res

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        print(f"Searching and downloading for '{arg}'...")
        result = download_region_by_name(arg)
        print("Result:", json.dumps(result, indent=2))
    else:
        print("Usage: python download_osm_region.py <city_or_location_name>")
