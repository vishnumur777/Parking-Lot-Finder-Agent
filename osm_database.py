"""
Offline OpenStreetMap Database Engine
Manages offline parking and spatial data using SQLite with Haversine distance calculations.
Works 100% offline without any external internet connection.
"""

import sqlite3
import math
import json
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "osm_parking.db")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in meters between two points
    on the earth (specified in decimal degrees).
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class OsmParkingDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes tables and indexes for offline parking spots."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS parking_spots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                osm_id TEXT UNIQUE NOT NULL,
                name TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                parking_type TEXT DEFAULT 'surface', -- surface, underground, multi-storey, street, garage
                capacity INTEGER DEFAULT 0,
                fee TEXT DEFAULT 'unknown',         -- free, yes, paid, '₹20/hr', etc.
                opening_hours TEXT DEFAULT '24/7',
                wheelchair TEXT DEFAULT 'unknown',   -- yes, no, limited
                operator TEXT,
                access TEXT DEFAULT 'public',        -- public, customers, private, permissive
                street TEXT,
                city TEXT,
                tags JSON
            );
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_parking_coords 
            ON parking_spots(latitude, longitude);
            """)
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_parking_city 
            ON parking_spots(city);
            """)
            conn.commit()

    def add_parking_spot(self, spot: Dict[str, Any]) -> bool:
        """Insert or replace a parking spot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO parking_spots (
                osm_id, name, latitude, longitude, parking_type, capacity,
                fee, opening_hours, wheelchair, operator, access, street, city, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(spot.get("osm_id", "")),
                spot.get("name", "Public Parking"),
                float(spot["latitude"]),
                float(spot["longitude"]),
                spot.get("parking_type", "surface"),
                int(spot.get("capacity", 0) or 0),
                spot.get("fee", "unknown"),
                spot.get("opening_hours", "24/7"),
                spot.get("wheelchair", "unknown"),
                spot.get("operator", ""),
                spot.get("access", "public"),
                spot.get("street", ""),
                spot.get("city", ""),
                json.dumps(spot.get("tags", {}))
            ))
            conn.commit()
            return True

    def bulk_add_parking_spots(self, spots: List[Dict[str, Any]]) -> int:
        """Bulk insert parking spots."""
        inserted = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for spot in spots:
                try:
                    cursor.execute("""
                    INSERT OR REPLACE INTO parking_spots (
                        osm_id, name, latitude, longitude, parking_type, capacity,
                        fee, opening_hours, wheelchair, operator, access, street, city, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        str(spot.get("osm_id", f"node_{inserted+1}")),
                        spot.get("name", "Public Parking"),
                        float(spot["latitude"]),
                        float(spot["longitude"]),
                        spot.get("parking_type", "surface"),
                        int(spot.get("capacity", 0) or 0),
                        spot.get("fee", "unknown"),
                        spot.get("opening_hours", "24/7"),
                        spot.get("wheelchair", "unknown"),
                        spot.get("operator", ""),
                        spot.get("access", "public"),
                        spot.get("street", ""),
                        spot.get("city", ""),
                        json.dumps(spot.get("tags", {}))
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"Error inserting spot: {e}")
            conn.commit()
        return inserted

    def search_nearby_parking(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 5000.0,
        parking_type: str = "any",
        fee_filter: str = "any",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search parking spots within radius_meters of (latitude, longitude).
        Uses a bounding box query in SQL for speed, followed by exact Haversine calculation.
        """
        # Bounding box calculation (approx 1 deg lat ~ 111,000m)
        lat_delta = radius_meters / 111000.0
        # cos(lat) accounts for longitude compression towards poles
        cos_lat = math.cos(math.radians(latitude))
        lon_delta = radius_meters / (111000.0 * max(cos_lat, 0.0001))

        min_lat = latitude - lat_delta
        max_lat = latitude + lat_delta
        min_lon = longitude - lon_delta
        max_lon = longitude + lon_delta

        query = """
        SELECT id, osm_id, name, latitude, longitude, parking_type, capacity,
               fee, opening_hours, wheelchair, operator, access, street, city, tags
        FROM parking_spots
        WHERE latitude BETWEEN ? AND ?
          AND longitude BETWEEN ? AND ?
        """
        params = [min_lat, max_lat, min_lon, max_lon]

        if parking_type and parking_type.lower() != "any":
            query += " AND LOWER(parking_type) = ?"
            params.append(parking_type.lower())

        if fee_filter and fee_filter.lower() != "any":
            if fee_filter.lower() == "free":
                query += " AND (LOWER(fee) IN ('no', 'free', '0') OR fee IS NULL)"
            elif fee_filter.lower() == "paid":
                query += " AND LOWER(fee) NOT IN ('no', 'free', '0')"

        candidates = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                dist = haversine_distance(latitude, longitude, row["latitude"], row["longitude"])
                if dist <= radius_meters:
                    item = dict(row)
                    item["distance_meters"] = round(dist, 1)
                    item["distance_text"] = f"{int(round(dist))} m" if dist < 1000 else f"{round(dist/1000.0, 1)} km"
                    try:
                        item["tags"] = json.loads(item["tags"]) if item["tags"] else {}
                    except Exception:
                        item["tags"] = {}
                    candidates.append(item)

        # Sort by distance
        candidates.sort(key=lambda x: x["distance_meters"])
        return candidates[:limit]

    def get_spot_by_osm_id(self, osm_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM parking_spots WHERE osm_id = ?", (str(osm_id),))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                try:
                    res["tags"] = json.loads(res["tags"]) if res["tags"] else {}
                except Exception:
                    res["tags"] = {}
                return res
        return None

    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM parking_spots")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(DISTINCT city) as cities FROM parking_spots WHERE city IS NOT NULL AND city != ''")
            cities = cursor.fetchone()["cities"]

            cursor.execute("""
            SELECT parking_type, COUNT(*) as cnt 
            FROM parking_spots 
            GROUP BY parking_type 
            ORDER BY cnt DESC
            """)
            type_distribution = {row["parking_type"]: row["cnt"] for row in cursor.fetchall()}

            return {
                "total_parking_spots": total,
                "indexed_cities": cities,
                "type_distribution": type_distribution,
                "database_path": self.db_path
            }

    def seed_default_offline_dataset(self):
        """Populates rich default parking data for Chennai and major locations if empty."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM parking_spots")
            count = cursor.fetchone()["cnt"]
            if count > 0:
                return count

        print("Seeding initial offline OSM parking dataset...")
        spots = [
            # Chennai Central / Park Station Area (Lat: 13.0827, Lon: 80.2707)
            {
                "osm_id": "osm_node_3001",
                "name": "Chennai Central Railway Multi-Level Car Parking",
                "latitude": 13.0833,
                "longitude": 80.2755,
                "parking_type": "multi-storey",
                "capacity": 350,
                "fee": "₹30/hr",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "Southern Railway",
                "access": "public",
                "street": "EVR Periyar Salai, Kannappar Thidal",
                "city": "Chennai",
                "tags": {"level": "4", "cctv": "yes", "ev_charging": "yes", "amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3002",
                "name": "Chennai Central Metro Underground Parking",
                "latitude": 13.0815,
                "longitude": 80.2740,
                "parking_type": "underground",
                "capacity": 200,
                "fee": "₹20/hr",
                "opening_hours": "05:00-23:00",
                "wheelchair": "yes",
                "operator": "CMRL",
                "access": "public",
                "street": "Poonamallee High Road",
                "city": "Chennai",
                "tags": {"underground": "yes", "security": "guarded", "amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3003",
                "name": "Ripon Building Municipal Parking",
                "latitude": 13.0820,
                "longitude": 80.2718,
                "parking_type": "surface",
                "capacity": 85,
                "fee": "free",
                "opening_hours": "08:00-20:00",
                "wheelchair": "yes",
                "operator": "Greater Chennai Corporation",
                "access": "public",
                "street": "Raja Muthiah Road",
                "city": "Chennai",
                "tags": {"surface": "paved", "amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3004",
                "name": "Victoria Public Hall Visitor Parking",
                "latitude": 13.0838,
                "longitude": 80.2730,
                "parking_type": "surface",
                "capacity": 60,
                "fee": "free",
                "opening_hours": "09:00-18:00",
                "wheelchair": "no",
                "operator": "GCC",
                "access": "public",
                "street": "EVR Periyar Salai",
                "city": "Chennai",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3005",
                "name": "Moore Market Two-Wheeler & Car Stand",
                "latitude": 13.0845,
                "longitude": 80.2762,
                "parking_type": "surface",
                "capacity": 150,
                "fee": "₹15/hr",
                "opening_hours": "06:00-22:00",
                "wheelchair": "limited",
                "operator": "Private Licensed",
                "access": "public",
                "street": "Park Town Commercial Street",
                "city": "Chennai",
                "tags": {"motorcycle_friendly": "yes", "amenity": "parking"}
            },

            # T. Nagar Area (Lat: 13.0418, Lon: 80.2341)
            {
                "osm_id": "osm_node_3010",
                "name": "T. Nagar Multi-Level Automated Car Parking (MLCP)",
                "latitude": 13.0410,
                "longitude": 80.2335,
                "parking_type": "multi-storey",
                "capacity": 550,
                "fee": "₹20/hr",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "Greater Chennai Corporation & Smart City",
                "access": "public",
                "street": "Thanikachalam Road",
                "city": "Chennai",
                "tags": {"automated": "yes", "levels": "6", "ev_charging": "yes", "amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3011",
                "name": "Pondy Bazaar Pedestrian Plaza Underground Parking",
                "latitude": 13.0425,
                "longitude": 80.2355,
                "parking_type": "underground",
                "capacity": 120,
                "fee": "₹25/hr",
                "opening_hours": "08:00-23:00",
                "wheelchair": "yes",
                "operator": "Smart City Chennai",
                "access": "public",
                "street": "Sir Thyagaraya Road",
                "city": "Chennai",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3012",
                "name": "Panagal Park Public Parking Lot",
                "latitude": 13.0402,
                "longitude": 80.2318,
                "parking_type": "surface",
                "capacity": 75,
                "fee": "free",
                "opening_hours": "06:00-21:00",
                "wheelchair": "yes",
                "operator": "Corporation",
                "access": "public",
                "street": "Nageswaran Road",
                "city": "Chennai",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3013",
                "name": "Ranganathan Street Customer Parking Garage",
                "latitude": 13.0440,
                "longitude": 80.2320,
                "parking_type": "garage",
                "capacity": 180,
                "fee": "₹30/hr",
                "opening_hours": "08:30-22:30",
                "wheelchair": "limited",
                "operator": "Merchant Association",
                "access": "public",
                "street": "Usman Road",
                "city": "Chennai",
                "tags": {"amenity": "parking"}
            },

            # Thiruvallur Area (Lat: 13.1437, Lon: 79.9080)
            {
                "osm_id": "osm_node_3020",
                "name": "Thiruvallur Railway Station Parking Yard",
                "latitude": 13.1450,
                "longitude": 79.9100,
                "parking_type": "surface",
                "capacity": 250,
                "fee": "₹10/day",
                "opening_hours": "24/7",
                "wheelchair": "limited",
                "operator": "Southern Railway",
                "access": "public",
                "street": "Station Road",
                "city": "Thiruvallur",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3021",
                "name": "Veeraraghava Swamy Temple Pilgrim Parking",
                "latitude": 13.1420,
                "longitude": 79.9065,
                "parking_type": "surface",
                "capacity": 180,
                "fee": "free",
                "opening_hours": "05:00-21:30",
                "wheelchair": "yes",
                "operator": "HR&CE Dept",
                "access": "public",
                "street": "Sannadhi Street",
                "city": "Thiruvallur",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3022",
                "name": "Thiruvallur Collectorate Complex Staff & Public Parking",
                "latitude": 13.1390,
                "longitude": 79.9130,
                "parking_type": "surface",
                "capacity": 110,
                "fee": "free",
                "opening_hours": "08:30-18:30",
                "wheelchair": "yes",
                "operator": "District Administration",
                "access": "public",
                "street": "JN Road",
                "city": "Thiruvallur",
                "tags": {"amenity": "parking"}
            },

            # Anna Nagar Area (Lat: 13.0850, Lon: 80.2100)
            {
                "osm_id": "osm_node_3030",
                "name": "Anna Nagar Tower Park Community Parking",
                "latitude": 13.0862,
                "longitude": 80.2115,
                "parking_type": "surface",
                "capacity": 130,
                "fee": "free",
                "opening_hours": "05:00-21:00",
                "wheelchair": "yes",
                "operator": "GCC",
                "access": "public",
                "street": "3rd Avenue",
                "city": "Chennai",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3031",
                "name": "Anna Nagar Roundtana Underground Metro Parking",
                "latitude": 13.0840,
                "longitude": 80.2120,
                "parking_type": "underground",
                "capacity": 160,
                "fee": "₹20/hr",
                "opening_hours": "05:30-23:00",
                "wheelchair": "yes",
                "operator": "CMRL",
                "access": "public",
                "street": "2nd Avenue",
                "city": "Chennai",
                "tags": {"ev_charging": "yes", "amenity": "parking"}
            },

            # Marina Beach Area (Lat: 13.0500, Lon: 80.2824)
            {
                "osm_id": "osm_node_3040",
                "name": "Marina Beach Promenade Parking Lot",
                "latitude": 13.0520,
                "longitude": 80.2830,
                "parking_type": "surface",
                "capacity": 400,
                "fee": "₹20/hr",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "GCC Parking Authority",
                "access": "public",
                "street": "Kamarajar Salai",
                "city": "Chennai",
                "tags": {"beach_access": "yes", "amenity": "parking"}
            },
            {
                "osm_id": "osm_node_3041",
                "name": "Santhome Cathedral Parking Ground",
                "latitude": 13.0335,
                "longitude": 80.2780,
                "parking_type": "surface",
                "capacity": 90,
                "fee": "free",
                "opening_hours": "06:00-21:00",
                "wheelchair": "yes",
                "operator": "Basilica Admin",
                "access": "public",
                "street": "Santhome High Road",
                "city": "Chennai",
                "tags": {"amenity": "parking"}
            },

            # Koyambedu CMBT Area (Lat: 13.0694, Lon: 80.2057)
            {
                "osm_id": "osm_node_3050",
                "name": "Koyambedu CMBT Bus Terminus Multi-Level Parking",
                "latitude": 13.0688,
                "longitude": 80.2045,
                "parking_type": "multi-storey",
                "capacity": 600,
                "fee": "₹25/hr",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "CMDA",
                "access": "public",
                "street": "Inner Ring Road",
                "city": "Chennai",
                "tags": {"amenity": "parking", "levels": "5"}
            },

            # Redhills Area (Lat: 13.1929, Lon: 80.1840)
            {
                "osm_id": "osm_redhills_01",
                "name": "Red Hills MTC Bus Terminus Parking",
                "latitude": 13.1929,
                "longitude": 80.1840,
                "parking_type": "surface",
                "capacity": 120,
                "fee": "₹10/day",
                "opening_hours": "04:30-23:30",
                "wheelchair": "yes",
                "operator": "MTC Chennai & GCC",
                "access": "public",
                "street": "Grand Northern Trunk Road (GNT Road / Old NH5)",
                "city": "Redhills",
                "tags": {"amenity": "parking", "bus_terminus": "yes", "two_wheeler": "yes"}
            },
            {
                "osm_id": "osm_redhills_02",
                "name": "Redhills Market Commercial Parking",
                "latitude": 13.1898,
                "longitude": 80.1874,
                "parking_type": "surface",
                "capacity": 80,
                "fee": "free",
                "opening_hours": "05:00-21:00",
                "wheelchair": "limited",
                "operator": "Redhills Town Panchayat",
                "access": "public",
                "street": "Market Street, GNT Road",
                "city": "Redhills",
                "tags": {"amenity": "parking", "market": "yes"}
            },
            {
                "osm_id": "way_1075064989",
                "name": "Red Hills Lorry Stop & Heavy Vehicle Layby",
                "latitude": 13.24156,
                "longitude": 80.22339,
                "parking_type": "surface",
                "capacity": 200,
                "fee": "₹50/day",
                "opening_hours": "24/7",
                "wheelchair": "no",
                "operator": "NHAI & Lorry Owners Association",
                "access": "public",
                "street": "NH16 / GNT Expressway",
                "city": "Redhills",
                "tags": {"amenity": "parking", "parking": "layby", "heavy_vehicles": "yes"}
            },
            {
                "osm_id": "osm_redhills_03",
                "name": "Naravarikuppam Public Vehicle Parking",
                "latitude": 13.1950,
                "longitude": 80.1820,
                "parking_type": "surface",
                "capacity": 65,
                "fee": "free",
                "opening_hours": "06:00-22:00",
                "wheelchair": "yes",
                "operator": "Naravarikuppam Municipality",
                "access": "public",
                "street": "Redhills-Tiruvallur High Road",
                "city": "Redhills",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_redhills_04",
                "name": "Puzhal Lake Promenade Visitor Parking",
                "latitude": 13.1825,
                "longitude": 80.1780,
                "parking_type": "surface",
                "capacity": 95,
                "fee": "free",
                "opening_hours": "05:30-20:00",
                "wheelchair": "yes",
                "operator": "Water Resources Dept & GCC",
                "access": "public",
                "street": "Lake View Road, Puzhal",
                "city": "Redhills",
                "tags": {"amenity": "parking", "park": "yes"}
            },
            {
                "osm_id": "way_403011444",
                "name": "Velammal Campus Visitor & Staff Parking",
                "latitude": 13.14954,
                "longitude": 80.19169,
                "parking_type": "surface",
                "capacity": 150,
                "fee": "free",
                "opening_hours": "07:30-19:00",
                "wheelchair": "yes",
                "operator": "Velammal Trust",
                "access": "public",
                "street": "Ambattur-Redhills Road, Surapet",
                "city": "Redhills",
                "tags": {"amenity": "parking", "surface": "paved"}
            },
            {
                "osm_id": "way_1533858486",
                "name": "Surapet-Redhills Bus Parking Ground",
                "latitude": 13.14637,
                "longitude": 80.19224,
                "parking_type": "surface",
                "capacity": 110,
                "fee": "free",
                "opening_hours": "06:00-20:00",
                "wheelchair": "no",
                "operator": "Institutional",
                "access": "public",
                "street": "Surapet Main Road",
                "city": "Redhills",
                "tags": {"amenity": "parking", "surface": "ground"}
            },
            {
                "osm_id": "way_1533858487",
                "name": "Redhills South Two-Wheeler Stand",
                "latitude": 13.14720,
                "longitude": 80.19282,
                "parking_type": "surface",
                "capacity": 85,
                "fee": "₹10/day",
                "opening_hours": "06:30-20:30",
                "wheelchair": "limited",
                "operator": "Town Panchayat",
                "access": "public",
                "street": "Redhills Road",
                "city": "Redhills",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_redhills_05",
                "name": "NH16 Karanodai-Redhills Commercial Layby",
                "latitude": 13.2180,
                "longitude": 80.1960,
                "parking_type": "surface",
                "capacity": 140,
                "fee": "free",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "NHAI",
                "access": "public",
                "street": "Karanodai Bypass, NH16",
                "city": "Redhills",
                "tags": {"amenity": "parking", "highway": "rest_area"}
            },
            {
                "osm_id": "osm_redhills_06",
                "name": "Vadakarai Commercial Center Parking",
                "latitude": 13.1985,
                "longitude": 80.1860,
                "parking_type": "surface",
                "capacity": 50,
                "fee": "free",
                "opening_hours": "08:00-22:00",
                "wheelchair": "yes",
                "operator": "Local Commercial Assoc",
                "access": "public",
                "street": "GNT Road",
                "city": "Redhills",
                "tags": {"amenity": "parking"}
            },

            # Gummidipoondi Area (Lat: 13.4098, Lon: 80.1237)
            {
                "osm_id": "osm_gummidipoondi_01",
                "name": "Gummidipoondi Railway Station 2-Wheeler & Car Stand",
                "latitude": 13.4098,
                "longitude": 80.1237,
                "parking_type": "surface",
                "capacity": 300,
                "fee": "₹10/day",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "Southern Railway (Chennai Suburban)",
                "access": "public",
                "street": "Station Approach Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "railway": "station", "two_wheeler": "yes", "cctv": "yes"}
            },
            {
                "osm_id": "osm_gummidipoondi_02",
                "name": "Gummidipoondi Bus Stand Public Parking",
                "latitude": 13.4110,
                "longitude": 80.1260,
                "parking_type": "surface",
                "capacity": 90,
                "fee": "free",
                "opening_hours": "05:00-23:00",
                "wheelchair": "yes",
                "operator": "Gummidipoondi Town Panchayat",
                "access": "public",
                "street": "Bazaar Street, GNT Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "bus_station": "yes"}
            },
            {
                "osm_id": "osm_gummidipoondi_03",
                "name": "SIPCOT Gummidipoondi Truck Terminal & Parking Yard",
                "latitude": 13.4136,
                "longitude": 80.0996,
                "parking_type": "surface",
                "capacity": 350,
                "fee": "₹40/day",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "SIPCOT Industrial Authority",
                "access": "public",
                "street": "SIPCOT Main Expressway Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "industrial": "yes", "heavy_vehicles": "yes"}
            },
            {
                "osm_id": "way_1499507182",
                "name": "RMK Engineering College Parking Ground",
                "latitude": 13.35713,
                "longitude": 80.14137,
                "parking_type": "surface",
                "capacity": 220,
                "fee": "free",
                "opening_hours": "07:00-19:00",
                "wheelchair": "yes",
                "operator": "Lakshmikanthammal Educational Trust",
                "access": "public",
                "street": "RSM Nagar, NH16",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "surface": "paved"}
            },
            {
                "osm_id": "osm_gummidipoondi_04",
                "name": "Kavaraippettai Station Two-Wheeler Stand",
                "latitude": 13.3645,
                "longitude": 80.1430,
                "parking_type": "surface",
                "capacity": 120,
                "fee": "₹10/day",
                "opening_hours": "05:00-23:00",
                "wheelchair": "limited",
                "operator": "Southern Railway",
                "access": "public",
                "street": "Kavaraippettai Station Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "railway": "yes"}
            },
            {
                "osm_id": "osm_gummidipoondi_05",
                "name": "SIPCOT Phase II Commercial Vehicle Layby",
                "latitude": 13.4350,
                "longitude": 80.1080,
                "parking_type": "surface",
                "capacity": 180,
                "fee": "free",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "SIPCOT",
                "access": "public",
                "street": "Industrial Ring Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "layby": "yes"}
            },
            {
                "osm_id": "osm_gummidipoondi_06",
                "name": "NH16 Gummidipoondi Highway Rest Area & Parking",
                "latitude": 13.4190,
                "longitude": 80.1340,
                "parking_type": "surface",
                "capacity": 160,
                "fee": "free",
                "opening_hours": "24/7",
                "wheelchair": "yes",
                "operator": "NHAI",
                "access": "public",
                "street": "NH16 Kolkata Highway",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "highway": "services"}
            },
            {
                "osm_id": "osm_gummidipoondi_07",
                "name": "Elavur Station Public Vehicle Parking",
                "latitude": 13.4560,
                "longitude": 80.1220,
                "parking_type": "surface",
                "capacity": 80,
                "fee": "free",
                "opening_hours": "05:00-22:30",
                "wheelchair": "yes",
                "operator": "Southern Railway",
                "access": "public",
                "street": "Elavur Station Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking"}
            },
            {
                "osm_id": "osm_gummidipoondi_08",
                "name": "Gummidipoondi Taluk Administrative Office Parking",
                "latitude": 13.4140,
                "longitude": 80.1285,
                "parking_type": "surface",
                "capacity": 70,
                "fee": "free",
                "opening_hours": "08:30-18:00",
                "wheelchair": "yes",
                "operator": "Thiruvallur District Revenue Dept",
                "access": "public",
                "street": "Taluk Office Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking", "government": "yes"}
            },
            {
                "osm_id": "osm_gummidipoondi_09",
                "name": "Madharpakkam Road Market Parking",
                "latitude": 13.4210,
                "longitude": 80.1190,
                "parking_type": "surface",
                "capacity": 55,
                "fee": "free",
                "opening_hours": "07:00-22:00",
                "wheelchair": "yes",
                "operator": "Town Panchayat",
                "access": "public",
                "street": "Gummidipoondi-Madharpakkam Road",
                "city": "Gummidipoondi",
                "tags": {"amenity": "parking"}
            }
        ]

        inserted = self.bulk_add_parking_spots(spots)
        print(f"Successfully seeded {inserted} offline OSM parking locations.")
        return inserted

if __name__ == "__main__":
    db = OsmParkingDatabase()
    db.seed_default_offline_dataset()
    print("Database stats:", db.get_stats())
    sample = db.search_nearby_parking(13.0827, 80.2707, radius_meters=1500)
    print(f"Found {len(sample)} spots near Chennai Central:")
    for s in sample:
        print(f" - {s['name']} ({s['distance_text']}, {s['capacity']} slots, {s['fee']}, {s['parking_type']})")
