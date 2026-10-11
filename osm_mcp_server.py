"""
OpenStreetMap Model Context Protocol (MCP) Server
Provides 100% offline tools for searching OpenStreetMap parking places,
retrieving parking metadata, and geocoding locations from local SQLite storage.
Complies with the MCP specification (MCP 2.x).
"""

import os
import sys
import json
from typing import List, Dict, Any, Optional
from osm_database import OsmParkingDatabase

# Geocoding landmark lookup for offline named queries
OFFLINE_LANDMARKS = {
    "chennai": {"lat": 13.0827, "lon": 80.2707, "name": "Chennai City Center"},
    "chennai central": {"lat": 13.0827, "lon": 80.2707, "name": "Chennai Central Railway Station"},
    "central railway station": {"lat": 13.0827, "lon": 80.2707, "name": "Puratchi Thalaivar Dr. M.G. Ramachandran Central Railway Station"},
    "ripon building": {"lat": 13.0820, "lon": 80.2718, "name": "Ripon Building Corporation Headquarters"},
    "t nagar": {"lat": 13.0418, "lon": 80.2341, "name": "T. Nagar (Thyagaraya Nagar)"},
    "thyagaraya nagar": {"lat": 13.0418, "lon": 80.2341, "name": "Thyagaraya Nagar"},
    "pondy bazaar": {"lat": 13.0425, "lon": 80.2355, "name": "Pondy Bazaar Pedestrian Plaza"},
    "panagal park": {"lat": 13.0402, "lon": 80.2318, "name": "Panagal Park"},
    "anna nagar": {"lat": 13.0850, "lon": 80.2100, "name": "Anna Nagar"},
    "anna nagar tower": {"lat": 13.0862, "lon": 80.2115, "name": "Anna Nagar Tower Park"},
    "marina beach": {"lat": 13.0500, "lon": 80.2824, "name": "Marina Beach"},
    "santhome": {"lat": 13.0335, "lon": 80.2780, "name": "Santhome Cathedral Basilica"},
    "koyambedu": {"lat": 13.0694, "lon": 80.2057, "name": "Koyambedu CMBT"},
    "cmbt": {"lat": 13.0688, "lon": 80.2045, "name": "Chennai Mofussil Bus Terminus (CMBT)"},
    "thiruvallur": {"lat": 13.1437, "lon": 79.9080, "name": "Thiruvallur Town"},
    "thiruvallur station": {"lat": 13.1450, "lon": 79.9100, "name": "Thiruvallur Railway Station"},
    "veeraraghava temple": {"lat": 13.1420, "lon": 79.9065, "name": "Sri Veeraraghava Swamy Temple, Thiruvallur"},
    "thiruvallur collectorate": {"lat": 13.1390, "lon": 79.9130, "name": "Thiruvallur Collectorate Complex"},
    # Redhills & North Chennai
    "redhills": {"lat": 13.1929, "lon": 80.1840, "name": "Red Hills Town & Bus Terminus"},
    "red hills": {"lat": 13.1929, "lon": 80.1840, "name": "Red Hills Town & Bus Terminus"},
    "redhills bus terminus": {"lat": 13.1929, "lon": 80.1840, "name": "Red Hills MTC Bus Terminus"},
    "redhills market": {"lat": 13.1898, "lon": 80.1874, "name": "Redhills Daily Market"},
    "naravarikuppam": {"lat": 13.1950, "lon": 80.1820, "name": "Naravarikuppam Redhills"},
    "puzhal": {"lat": 13.1825, "lon": 80.1780, "name": "Puzhal Lake Promenade Area"},
    "puzhal lake": {"lat": 13.1825, "lon": 80.1780, "name": "Puzhal Lake Promenade Area"},
    # Gummidipoondi & Industrial Corridor
    "gummidipoondi": {"lat": 13.4098, "lon": 80.1237, "name": "Gummidipoondi Town & Railway Station"},
    "gummidipundi": {"lat": 13.4098, "lon": 80.1237, "name": "Gummidipoondi Town & Railway Station"},
    "gummidipoondi station": {"lat": 13.4098, "lon": 80.1237, "name": "Gummidipoondi Railway Station"},
    "gummidipoondi railway station": {"lat": 13.4098, "lon": 80.1237, "name": "Gummidipoondi Railway Station"},
    "gummidipoondi bus stand": {"lat": 13.4110, "lon": 80.1260, "name": "Gummidipoondi Bus Stand"},
    "sipcot gummidipoondi": {"lat": 13.4136, "lon": 80.0996, "name": "SIPCOT Industrial Complex, Gummidipoondi"},
    "kavaraippettai": {"lat": 13.3645, "lon": 80.1430, "name": "Kavaraippettai Station"},
    "elavur": {"lat": 13.4560, "lon": 80.1220, "name": "Elavur Station"},
}

class OsmMcpTools:
    """Core logic for OSM MCP tools, usable both in-process and via MCP protocol."""
    def __init__(self, db: Optional[OsmParkingDatabase] = None):
        self.db = db or OsmParkingDatabase()
        # Seed default dataset if database is newly initialized
        self.db.seed_default_offline_dataset()

    def search_parking(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 5000.0,
        parking_type: str = "any",
        fee_filter: str = "any",
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search offline OpenStreetMap database for nearby parking places.
        
        Args:
            latitude: Latitude of the search origin (e.g. 13.0827).
            longitude: Longitude of the search origin (e.g. 80.2707).
            radius_meters: Radius in meters (default 5000m / 5km).
            parking_type: Type of parking ('any', 'surface', 'underground', 'multi-storey', 'garage').
            fee_filter: Filter fee status ('any', 'free', 'paid').
            limit: Maximum number of parking spots to return (default 5).
        """
        spots = self.db.search_nearby_parking(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            parking_type=parking_type,
            fee_filter=fee_filter,
            limit=limit
        )
        return spots

    def get_parking_details(self, osm_id: str) -> Dict[str, Any]:
        """
        Get full OpenStreetMap metadata and attributes for a specific parking spot.
        
        Args:
            osm_id: OpenStreetMap ID (e.g. 'osm_node_3001').
        """
        spot = self.db.get_spot_by_osm_id(osm_id)
        if not spot:
            return {"error": f"Parking spot with ID '{osm_id}' not found in offline OSM database."}
        return spot

    def geocode_offline(self, query: str) -> Dict[str, Any]:
        """
        Resolve landmark, station, or neighborhood names to coordinates offline.
        
        Args:
            query: Name of place or landmark (e.g. 'Chennai Central', 'T Nagar', 'Marina Beach').
        """
        cleaned = query.strip().lower()
        # Direct lookup
        if cleaned in OFFLINE_LANDMARKS:
            match = OFFLINE_LANDMARKS[cleaned]
            return {
                "found": True,
                "name": match["name"],
                "latitude": match["lat"],
                "longitude": match["lon"]
            }
        
        # Substring search
        for key, val in OFFLINE_LANDMARKS.items():
            if key in cleaned or cleaned in key:
                return {
                    "found": True,
                    "name": val["name"],
                    "latitude": val["lat"],
                    "longitude": val["lon"]
                }
        
        # Search parking spots by name or street in DB
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT name, latitude, longitude, street, city 
            FROM parking_spots 
            WHERE LOWER(name) LIKE ? OR LOWER(street) LIKE ? OR LOWER(city) LIKE ?
            LIMIT 1
            """, (f"%{cleaned}%", f"%{cleaned}%", f"%{cleaned}%"))
            row = cursor.fetchone()
            if row:
                return {
                    "found": True,
                    "name": row["name"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "street": row["street"],
                    "city": row["city"]
                }

        return {
            "found": False,
            "query": query,
            "message": "Place not found in offline index. Using default location coordinates."
        }

    def get_offline_map_stats(self) -> Dict[str, Any]:
        """Get statistics of the offline OpenStreetMap database."""
        return self.db.get_stats()


# MCP Server instantiation using official MCP SDK
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("openstreetmap-offline")
tools = OsmMcpTools()

@mcp.tool()
def search_parking(
    latitude: float,
    longitude: float,
    radius_meters: float = 5000.0,
    parking_type: str = "any",
    fee_filter: str = "any",
    limit: int = 5
) -> str:
    """
    Search offline OpenStreetMap database for nearby parking places.
    Returns JSON string with parking spots, distance, capacity, fee, and type.
    """
    results = tools.search_parking(latitude, longitude, radius_meters, parking_type, fee_filter, limit)
    return json.dumps(results, indent=2)

@mcp.tool()
def get_parking_details(osm_id: str) -> str:
    """
    Retrieve full OpenStreetMap attributes for a specific parking spot ID.
    """
    result = tools.get_parking_details(osm_id)
    return json.dumps(result, indent=2)

@mcp.tool()
def geocode_offline(query: str) -> str:
    """
    Resolve a city, station, or landmark name to coordinates using offline OSM index.
    """
    result = tools.geocode_offline(query)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_offline_map_stats() -> str:
    """
    Returns statistics regarding the offline OpenStreetMap database.
    """
    result = tools.get_offline_map_stats()
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        # Run standard MCP server over stdio
        mcp.run("stdio")
    else:
        # Run test inspection
        print("--- OpenStreetMap Offline MCP Server Tools ---")
        sample = tools.search_parking(13.0827, 80.2707, 1000)
        print(f"Sample query result: {len(sample)} spots found near Chennai Central")
        for s in sample:
            print(f"  • {s['name']}: {s['distance_text']}, {s['capacity']} capacity, fee: {s['fee']}")
        print("\nOffline stats:", json.dumps(tools.get_offline_map_stats(), indent=2))
