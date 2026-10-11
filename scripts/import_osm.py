"""
Offline OpenStreetMap Importer
Imports OSM features (from Overpass JSON, GeoJSON, or custom JSON) into local SQLite storage.
Ensures 100% offline availability of map points of interest.
"""

import os
import sys
import json
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from osm_database import OsmParkingDatabase

def parse_overpass_json(data: Dict[str, Any], default_city: str = "") -> List[Dict[str, Any]]:
    """Parses standard Overpass API JSON elements into parking records."""
    spots = []
    elements = data.get("elements", [])
    
    for el in elements:
        tags = el.get("tags", {})
        amenity = tags.get("amenity", "")
        if amenity != "parking" and "parking" not in tags:
            continue

        osm_id = f"{el.get('type', 'node')}_{el.get('id', '')}"
        
        # Determine latitude and longitude
        lat = el.get("lat")
        lon = el.get("lon")
        
        # If way or relation, Overpass often includes center or bounds
        if lat is None or lon is None:
            center = el.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            continue

        name = tags.get("name") or tags.get("description") or f"Public Parking {osm_id}"
        parking_type = tags.get("parking", "surface")
        if "underground" in tags.get("location", "") or tags.get("underground") == "yes":
            parking_type = "underground"
        elif tags.get("building") == "parking" or tags.get("parking") == "multi-storey":
            parking_type = "multi-storey"

        capacity_raw = tags.get("capacity", "0")
        try:
            capacity = int(capacity_raw)
        except Exception:
            capacity = 0

        fee = tags.get("fee", "unknown")
        if fee == "no":
            fee = "free"
        elif tags.get("charge"):
            fee = tags.get("charge")

        opening_hours = tags.get("opening_hours", "24/7")
        wheelchair = tags.get("wheelchair", "unknown")
        operator = tags.get("operator", "")
        access = tags.get("access", "public")
        street = tags.get("addr:street", "")
        city = tags.get("addr:city", default_city)

        spots.append({
            "osm_id": osm_id,
            "name": name,
            "latitude": float(lat),
            "longitude": float(lon),
            "parking_type": parking_type,
            "capacity": capacity,
            "fee": fee,
            "opening_hours": opening_hours,
            "wheelchair": wheelchair,
            "operator": operator,
            "access": access,
            "street": street,
            "city": city,
            "tags": tags
        })

    return spots

def import_file(file_path: str, city: str = "") -> int:
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return 0

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = OsmParkingDatabase()
    spots = []
    if "elements" in data:
        spots = parse_overpass_json(data, default_city=city)
    elif isinstance(data, list):
        spots = data
    elif "features" in data:
        # GeoJSON
        for f in data.get("features", []):
            geom = f.get("geometry", {})
            props = f.get("properties", {})
            coords = geom.get("coordinates", [0, 0])
            spots.append({
                "osm_id": str(props.get("id", f"node_{len(spots)}")),
                "name": props.get("name", "Public Parking"),
                "latitude": coords[1],
                "longitude": coords[0],
                "parking_type": props.get("parking", "surface"),
                "capacity": props.get("capacity", 0),
                "fee": props.get("fee", "unknown"),
                "city": city or props.get("city", ""),
                "tags": props
            })

    count = db.bulk_add_parking_spots(spots)
    print(f"Successfully imported {count} parking spots from {file_path} into offline database.")
    return count

if __name__ == "__main__":
    if len(sys.argv) > 1:
        import_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        print("Usage: python import_osm.py <path_to_json_or_geojson> [city_name]")
