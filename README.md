# ParkVoice - 100% Offline Voice OSM Parking PWA

An end-to-end **100% Offline Progressive Web App (PWA)** that allows users to ask parking questions via microphone, transcribe speech with offline Faster-Whisper STT, reason and call offline OpenStreetMap tools using **Qwen 3 (1.7B GGUF via llama.cpp)**, query a local **OpenStreetMap MCP Server**, and speak answers aloud using offline **Piper TTS**.

---

## 🏗️ Architecture

```
                                  USER (Voice Input)
                                         │
                                         ▼ [Microphone Capture]
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                           PARKVOICE OFFLINE PWA                             │
  │  • Service Worker (sw.js) for 100% Offline Caching                          │
  │  • Real-time Web Audio API Waveform Visualizer                              │
  │  • Interactive Offline Leaflet Map (Pins, Radar Radius, Popups)             │
  │  • Live MCP Tool Trace & Parking Result Cards                               │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │ HTTP / REST
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                        LOCAL OFFLINE BACKEND SERVER                         │
  │                             (FastAPI + Uvicorn)                             │
  │                                                                             │
  │  1. STT: Faster-Whisper (tiny.en int8) transcribes user audio in ~0.7s     │
  │  2. Agent Orchestrator bridges Qwen 3 with OpenStreetMap MCP Server         │
  │  3. TTS: Piper Neural TTS (en_US-lessac-medium) synthesizes voice in ~1.7s │
  └──────────────────┬──────────────────────────────────────┬───────────────────┘
                     │                                      │
                     ▼                                      ▼
  ┌────────────────────────────────────┐ ┌──────────────────────────────────────┐
  │          LLAMA.CPP SERVER          │ │     OPENSTREETMAP OFFLINE MCP SERVER │
  │  • Model: Qwen 3 (1.7B-Q4_0 GGUF)  │ │  • Model Context Protocol (MCP 2.x)  │
  │  • Port: 8089                      │ │  • SQLite Spatial Index (Haversine)  │
  │  • Native OpenAI Tool Calling API  │ │  • 234+ Offline Parking Spots Cached │
  │  • 100% Local Inference on CPU     │ │  • Tools: search_parking, geocode... │
  └────────────────────────────────────┘ └──────────────────────────────────────┘
```

---

## ⚡ Quick Start

### 1. Launch Everything in One Command
Run the master startup script:
```bash
./run.sh
```

This will automatically:
1. Start `llama.cpp` server on port `8089` loading the local `Qwen3-1.7B-Q4_0.gguf` model.
2. Verify offline SQLite database has the OpenStreetMap parking dataset.
3. Start the FastAPI backend and PWA on `http://127.0.0.1:8080`.

Open your browser to:
👉 **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

---

## 🎤 How It Works

1. **Microphone Capture**:
   - Tap the large glowing microphone button. The real-time Web Audio API visualizer animates live audio waveforms.
2. **Offline Speech-to-Text (STT)**:
   - Faster-Whisper (`tiny.en`, int8 quantized) transcribes the recording on CPU in under 1 second.
3. **Qwen 3 + OpenStreetMap MCP Server**:
   - Qwen 3 receives the user prompt and GPS coordinates.
   - It autonomously emits a tool call: `search_parking(latitude, longitude, radius_meters)`.
   - The OpenStreetMap MCP Server queries the local SQLite spatial database and returns matching parking records with sub-millisecond latency.
4. **Natural Spoken Response**:
   - Qwen 3 synthesizes a concise, driver-friendly summary (nearest spot, distance, capacity, fee).
5. **Offline Text-to-Speech (TTS)**:
   - Piper TTS generates a natural sounding 22 kHz WAV audio stream.
   - The PWA automatically plays the synthesized voice and updates the interactive map with parking markers.

---

## 🛠️ OpenStreetMap MCP Server Tools

The MCP Server (`osm_mcp_server.py`) implements the Model Context Protocol (MCP 2.x) and exposes:

| Tool Name | Parameters | Description |
|---|---|---|
| `search_parking` | `latitude`, `longitude`, `radius_meters`, `parking_type`, `fee_filter`, `limit` | Searches offline OSM database for parking spots near coordinates. |
| `get_parking_details` | `osm_id` | Retrieves full OpenStreetMap metadata, wheelchair info, operator, and tags. |
| `geocode_offline` | `query` | Resolves landmark names (e.g. "Chennai Central", "T Nagar") to coordinates offline. |
| `get_offline_map_stats` | None | Returns total indexed parking spots and category breakdowns. |

You can also run the MCP server over stdio for external MCP clients:
```bash
.venv/bin/python osm_mcp_server.py --stdio
```

---

## 🌍 Downloading Additional Offline Regions

The offline database currently ships with 234+ parking spots across Chennai, Thiruvallur, and key hubs.
When connected to the internet, you can easily download any other region to use offline:
```bash
# Download by city preset:
.venv/bin/python scripts/download_osm_region.py chennai
.venv/bin/python scripts/download_osm_region.py bangalore
.venv/bin/python scripts/download_osm_region.py mumbai

# Or download custom bounding box (south west north east):
.venv/bin/python scripts/download_osm_region.py 13.00 80.20 13.10 80.30
```
Or import any custom Overpass JSON / GeoJSON file:
```bash
.venv/bin/python scripts/import_osm.py path/to/parking.geojson "MyCity"
```

---

## 🧪 Testing

Run the full end-to-end integration test suite:
```bash
.venv/bin/python test_system.py
```
Validates all 5 layers:
1. SQLite spatial database queries
2. MCP server protocol tools
3. Piper TTS voice synthesis
4. Faster-Whisper STT transcription
5. Qwen 3 agent tool calling and reasoning loop

---

## 📱 PWA Features
- **100% Offline Installable**: Works offline via Service Worker (`sw.js`).
- **Interactive Leaflet Map**: Bundled local Leaflet JS/CSS with custom parking markers.
- **Audio Control Bar**: Scrub, replay, and control playback speed.
- **MCP Tool Inspector**: Real-time drawer showing raw JSON-RPC tool calls and responses.
