"""
Automated End-to-End System Test for ParkVoice Offline Stack
Tests:
1. Offline OSM Database
2. MCP Server Protocol Tools
3. Offline Piper TTS
4. Offline Faster-Whisper STT
5. Agent Orchestrator with Qwen 3 (llama.cpp)
"""

import sys
import os
import time
import asyncio
import io

from osm_database import OsmParkingDatabase
from osm_mcp_server import OsmMcpTools
from speech_engine import OfflineSpeechEngine
from agent_orchestrator import AgentOrchestrator

async def run_tests():
    print("==============================================================")
    print("    RUNNING 100% OFFLINE PARKVOICE SYSTEM INTEGRATION TEST   ")
    print("==============================================================")

    # Test 1: Database
    print("\n[1/5] Testing Offline OpenStreetMap Database...")
    db = OsmParkingDatabase()
    stats = db.get_stats()
    print(f"  • Total spots in offline DB: {stats['total_parking_spots']}")
    assert stats["total_parking_spots"] > 0, "DB has no spots!"
    spots = db.search_nearby_parking(13.0827, 80.2707, radius_meters=1500)
    print(f"  • Found {len(spots)} spots within 1500m of Chennai Central.")
    print(f"  • Nearest: {spots[0]['name']} ({spots[0]['distance_text']}, {spots[0]['fee']})")
    print("  ✓ Database test passed!")

    # Test 2: MCP Tools
    print("\n[2/5] Testing OpenStreetMap MCP Server Tools...")
    mcp = OsmMcpTools(db=db)
    geocoded = mcp.geocode_offline("Chennai Central")
    print(f"  • Geocoding 'Chennai Central' offline: {geocoded}")
    assert geocoded.get("found"), "Geocoding failed"
    mcp_spots = mcp.search_parking(geocoded["latitude"], geocoded["longitude"], radius_meters=1000)
    print(f"  • MCP search_parking returned {len(mcp_spots)} spots.")
    assert len(mcp_spots) > 0, "MCP search returned 0 spots"
    print("  ✓ MCP tools test passed!")

    # Test 3: Offline TTS
    print("\n[3/5] Testing Offline Piper Text-to-Speech...")
    speech = OfflineSpeechEngine()
    test_phrase = "I found three parking places near your destination."
    wav_bytes, t_tts = speech.synthesize_speech_wav(test_phrase)
    print(f"  • Synthesized {len(wav_bytes)} bytes in {t_tts:.2f}s")
    assert len(wav_bytes) > 1000, "TTS audio too small"
    print("  ✓ Offline TTS test passed!")

    # Test 4: Offline STT
    print("\n[4/5] Testing Offline Faster-Whisper Speech-to-Text...")
    transcript, t_stt = speech.transcribe_audio_bytes(wav_bytes)
    print(f"  • Transcribed audio in {t_stt:.2f}s: \"{transcript}\"")
    assert "parking" in transcript.lower(), "Whisper did not transcribe 'parking'"
    print("  ✓ Offline STT test passed!")

    # Test 5: LLM + MCP Agent Orchestrator
    print("\n[5/5] Testing Agent Orchestrator with Qwen 3 (llama.cpp)...")
    orch = AgentOrchestrator(mcp_tools=mcp, speech_engine=speech)
    llama_ok = await orch.check_llama_health()
    if not llama_ok:
        print("  ! llama.cpp is not currently running. Skipping live LLM call.")
        print("  ! (Start via ./run.sh to test live LLM).")
    else:
        print("  • llama.cpp server is reachable! Testing full query pipeline...")
        result = await orch.process_query(
            user_text="Find parking near me",
            user_lat=13.0827,
            user_lon=80.2707,
            radius_meters=1500,
            synthesize_tts=True
        )
        print(f"  • Spoken Answer: \"{result['answer']}\"")
        print(f"  • Found Spots: {len(result['parking_spots'])}")
        print(f"  • Tool Executions: {result['tool_executions']}")
        print(f"  • Timings: {result['timings']}")
        assert len(result["parking_spots"]) > 0
        assert result["audio_base64"] is not None
        print("  ✓ Agent Orchestrator test passed!")

    # Test 6: Dynamic Spot Count & Radius Constraints
    print("\n[6/6] Testing Dynamic Spot Count (10 spots) & Radius Constraints...")
    res_custom = await orch.process_query(
        user_text="Find 10 parking locations within 3 km",
        user_lat=13.0827,
        user_lon=80.2707,
        synthesize_tts=False
    )
    print(f"  • Extracted Effective Limit: {res_custom['effective_limit']}")
    print(f"  • Extracted Effective Radius: {res_custom['effective_radius']}m")
    print(f"  • Returned Spots Count: {len(res_custom['parking_spots'])}")
    assert res_custom["effective_limit"] == 10, "Effective limit was not 10"
    assert res_custom["effective_radius"] == 3000.0, "Effective radius was not 3000m"
    assert len(res_custom["parking_spots"]) == 10, f"Expected 10 spots, got {len(res_custom['parking_spots'])}"
    # Test 7: Offline Road Routing & Turn-by-Turn Navigation
    print("\n[7/7] Testing Offline Road Routing & Turn-by-Turn Navigation...")
    from routing_engine import OfflineRoutingEngine
    router = OfflineRoutingEngine()
    route = router.get_route(
        start_lat=13.1837,
        start_lon=80.1899,
        end_lat=13.0833,
        end_lon=80.2755,
        start_name="Redhills",
        end_name="Chennai Central"
    )
    print(f"  • Route Source: {route.get('source')}")
    print(f"  • Distance: {route.get('distance_text')}, Duration: {route.get('duration_text')}")
    print(f"  • Steps: {len(route.get('steps', []))} turn-by-turn maneuvers")
    assert len(route.get("steps", [])) > 0
    assert route.get("geometry") is not None
    print("  ✓ Road Routing & Turn-by-Turn Navigation test passed!")

    print("\n==============================================================")
    print("          ALL TEST SUITES PASSED SUCCESSFULLY!               ")
    print("==============================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
