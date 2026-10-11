"""
ParkVoice Offline PWA - Backend Server
Integrates:
- Faster-Whisper (100% Offline Speech-to-Text)
- Qwen 3 (1.7B GGUF via llama.cpp)
- OpenStreetMap MCP Server (100% Offline Spatial Database)
- Piper TTS (100% Offline Text-to-Speech)
- PWA Static Assets & Service Worker
"""

import os
import sys
import io
import time
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from osm_database import OsmParkingDatabase
from osm_mcp_server import OsmMcpTools
from speech_engine import OfflineSpeechEngine
from agent_orchestrator import AgentOrchestrator, LLAMA_SERVER_URL
from routing_engine import OfflineRoutingEngine
from scripts.download_osm_region import (
    download_parking_by_bbox,
    download_region_by_name,
    search_and_geocode_location,
    CITY_BBOXES
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="ParkVoice Offline PWA",
    description="100% Offline Voice-Enabled Parking Assistant powered by Qwen 3, llama.cpp, OSM MCP, Whisper, and Piper TTS",
    version="1.0.0"
)

# Enable CORS for local and PWA standalone execution
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    """Ensures browser and service worker always fetch the newest UI code on reload."""
    response = await call_next(request)
    if request.url.path.startswith("/static/") or request.url.path in ["/", "/sw.js", "/manifest.webmanifest"]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Initialize singletons
osm_db = OsmParkingDatabase()
mcp_tools = OsmMcpTools(db=osm_db)
speech_engine = OfflineSpeechEngine()
routing_engine = OfflineRoutingEngine(db_path=osm_db.db_path)
orchestrator = AgentOrchestrator(
    llama_url=LLAMA_SERVER_URL,
    mcp_tools=mcp_tools,
    speech_engine=speech_engine
)

class TextQueryRequest(BaseModel):
    text: str
    latitude: float = 13.0827
    longitude: float = 80.2707
    radius_meters: float = 5000.0
    synthesize_tts: bool = True

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    start_name: Optional[str] = "Starting Location"
    end_name: Optional[str] = "Parking Destination"
    synthesize_voice: Optional[bool] = True

@app.get("/api/status")
async def get_system_status():
    """Returns the operational status of all offline sub-systems."""
    llama_online = await orchestrator.check_llama_health()
    db_stats = osm_db.get_stats()
    
    return {
        "status": "healthy",
        "offline_ready": True,
        "subsystems": {
            "speech_to_text": {
                "engine": "Faster-Whisper (int8 CPU)",
                "model": speech_engine.whisper_model_size,
                "offline": True,
                "status": "ready"
            },
            "llm": {
                "engine": "llama.cpp",
                "model": "Qwen 3 (1.7B-Q4_0 GGUF)",
                "endpoint": orchestrator.llama_url,
                "offline": True,
                "status": "online" if llama_online else "offline"
            },
            "mcp_server": {
                "protocol": "Model Context Protocol (MCP 2.x)",
                "tools": ["search_parking", "get_parking_details", "geocode_offline", "get_offline_map_stats"],
                "offline": True,
                "status": "ready"
            },
            "text_to_speech": {
                "engine": "Piper TTS (ONNX)",
                "voice": "en_US-lessac-medium",
                "offline": True,
                "status": "ready"
            },
            "osm_database": {
                "storage": "SQLite + Spatial Haversine Index",
                "total_parking_spots": db_stats["total_parking_spots"],
                "indexed_cities": db_stats["indexed_cities"],
                "type_breakdown": db_stats["type_distribution"],
                "status": "ready"
            }
        }
    }

@app.post("/api/voice-query")
async def voice_query(
    audio: UploadFile = File(...),
    latitude: float = Form(13.0827),
    longitude: float = Form(80.2707),
    radius_meters: float = Form(5000.0)
):
    """
    Core Voice Pipeline:
    1. Audio -> Whisper STT (Offline) -> Transcribed Text
    2. Transcribed Text + GPS -> Qwen 3 (llama.cpp) -> Tool Call
    3. Tool Call -> OpenStreetMap MCP Server (Offline DB) -> Parking Spots
    4. Parking Spots -> Qwen 3 -> Synthesized Spoken Answer
    5. Answer -> Piper TTS (Offline) -> WAV Audio Base64
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes or len(audio_bytes) < 100:
            raise HTTPException(status_code=400, detail="Audio recording too short or empty")

        # Step 1: STT
        transcription, t_stt = speech_engine.transcribe_audio_bytes(audio_bytes)
        transcription_clean = transcription.strip()
        
        # If whisper heard nothing (silence or filtered noise), default gracefully
        query_text = transcription_clean if transcription_clean else "Find parking near me"

        # Step 2-5: Orchestrator Pipeline
        result = await orchestrator.process_query(
            user_text=query_text,
            user_lat=latitude,
            user_lon=longitude,
            radius_meters=radius_meters,
            synthesize_tts=True
        )
        
        result["transcription"] = transcription_clean or "No clear speech detected (searching nearby parking)"
        result["timings"]["stt"] = round(t_stt, 2)
        if "total" in result["timings"]:
            result["timings"]["total"] = round(result["timings"]["total"] + t_stt, 2)

        return JSONResponse(result)

    except Exception as e:
        print(f"[Error in voice_query]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def text_query(req: TextQueryRequest):
    """Text-based query through the same agentic workflow."""
    result = await orchestrator.process_query(
        user_text=req.text,
        user_lat=req.latitude,
        user_lon=req.longitude,
        radius_meters=req.radius_meters,
        synthesize_tts=req.synthesize_tts
    )
    result["transcription"] = req.text
    return JSONResponse(result)

@app.post("/api/stt")
async def transcribe_only(audio: UploadFile = File(...)):
    """Transcribes audio file to text offline."""
    audio_bytes = await audio.read()
    text, elapsed = speech_engine.transcribe_audio_bytes(audio_bytes)
    return {"text": text, "elapsed_seconds": round(elapsed, 2)}

@app.get("/api/tts")
def synthesize_only(text: str = Query(..., description="Text to synthesize")):
    """Synthesizes text into offline Piper WAV audio stream."""
    wav_bytes, elapsed = speech_engine.synthesize_speech_wav(text)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-Synthesis-Time": f"{elapsed:.3f}s"}
    )

@app.get("/api/parking/nearby")
def get_nearby_parking(
    latitude: float = Query(13.0827),
    longitude: float = Query(80.2707),
    radius_meters: float = Query(5000.0),
    parking_type: str = Query("any"),
    fee_filter: str = Query("any"),
    limit: int = Query(10)
):
    """Direct offline spatial search for parking places."""
    spots = mcp_tools.search_parking(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        parking_type=parking_type,
        fee_filter=fee_filter,
        limit=limit
    )
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius_meters": radius_meters,
        "count": len(spots),
        "parking_spots": spots
    }

@app.get("/api/search-region")
def search_region(query: str = Query(..., description="Location name or city to search in OpenStreetMap")):
    """Searches for any location or city and returns its geocoded coordinates and bounding box."""
    result = search_and_geocode_location(query)
    return result

@app.post("/api/download-region")
def download_region(
    city: str = Query("chennai"),
    south: Optional[float] = Query(None),
    west: Optional[float] = Query(None),
    north: Optional[float] = Query(None),
    east: Optional[float] = Query(None)
):
    """
    Downloads OpenStreetMap parking data for any searched location or bounding box.
    Tries Overpass mirrors; if none found, returns a clear status message.
    """
    city_clean = city.strip()
    
    if south is not None and west is not None and north is not None and east is not None:
        res = download_parking_by_bbox(south, west, north, east, city_name=city_clean)
        total_in_db = osm_db.get_stats()["total_parking_spots"]
        return {
            "city": city_clean,
            "success": res.get("success", False),
            "downloaded_spots": res.get("count", 0),
            "total_spots_in_db": total_in_db,
            "message": res.get("message", "")
        }

    res = download_region_by_name(city_clean)
    total_in_db = osm_db.get_stats()["total_parking_spots"]

    # If successful, register landmark into OFFLINE_LANDMARKS dynamically
    if res.get("success") and res.get("latitude") and res.get("longitude"):
        from osm_mcp_server import OFFLINE_LANDMARKS
        clean_key = city_clean.lower()
        OFFLINE_LANDMARKS[clean_key] = {
            "lat": res["latitude"],
            "lon": res["longitude"],
            "name": res.get("display_name", city_clean)
        }

    return {
        "city": res.get("city", city_clean),
        "display_name": res.get("display_name", city_clean),
        "latitude": res.get("latitude"),
        "longitude": res.get("longitude"),
        "bbox": res.get("bbox"),
        "success": res.get("success", False),
        "downloaded_spots": res.get("count", 0),
        "total_spots_in_db": total_in_db,
        "message": res.get("message", "")
    }

@app.post("/api/route")
async def calculate_route(req: RouteRequest):
    """
    Calculates road-following directions between starting point and parking destination.
    Priority: SQLite cache -> OSRM router (if network) -> Offline Geometric Road Graph Synthesizer.
    Synthesizes spoken turn-by-turn guidance via Piper TTS.
    """
    try:
        route_data = routing_engine.get_route(
            start_lat=req.start_lat,
            start_lon=req.start_lon,
            end_lat=req.end_lat,
            end_lon=req.end_lon,
            start_name=req.start_name or "Starting Location",
            end_name=req.end_name or "Parking Destination"
        )

        # Synthesize offline speech if requested
        if req.synthesize_voice and route_data.get("spoken_narrative"):
            try:
                audio_b64, _ = speech_engine.synthesize_speech_base64(route_data["spoken_narrative"])
                route_data["audio_base64"] = audio_b64
            except Exception as e:
                print(f"[calculate_route TTS error]: {e}")
                route_data["audio_base64"] = None
        else:
            route_data["audio_base64"] = None

        return JSONResponse(route_data)
    except Exception as e:
        print(f"[calculate_route error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/offline-regions")
def get_offline_regions():
    """
    Returns dynamic list of downloaded regions and their representative coordinates from SQLite database,
    along with spot counts for starting point selection.
    """
    try:
        with osm_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT city, COUNT(*) as spot_count, AVG(latitude) as avg_lat, AVG(longitude) as avg_lon
            FROM parking_spots
            WHERE city IS NOT NULL AND city != ''
            GROUP BY city
            ORDER BY spot_count DESC;
            """)
            rows = cursor.fetchall()
            regions = []
            for r in rows:
                regions.append({
                    "city": r["city"],
                    "spot_count": r["spot_count"],
                    "latitude": round(r["avg_lat"], 5),
                    "longitude": round(r["avg_lon"], 5)
                })

        return {
            "total_regions": len(regions),
            "regions": regions
        }
    except Exception as e:
        print(f"[get_offline_regions error]: {e}")
        return {"total_regions": 0, "regions": []}

# Mount static directory for PWA files
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "ParkVoice PWA static assets initializing..."}

@app.get("/sw.js")
def serve_sw():
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    return FileResponse(sw_path, media_type="application/javascript")

@app.get("/manifest.webmanifest")
def serve_manifest():
    manifest_path = os.path.join(STATIC_DIR, "manifest.webmanifest")
    return FileResponse(manifest_path, media_type="application/manifest+json")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=False)
