"""
Offline Agent Orchestrator
Connects Qwen 3 (running via llama.cpp) with the Offline OpenStreetMap MCP Server
and the Offline Speech Engine (Whisper STT + Piper TTS).
"""

import json
import time
import httpx
import re
from typing import List, Dict, Any, Optional, Tuple
from osm_mcp_server import OsmMcpTools
from speech_engine import OfflineSpeechEngine

LLAMA_SERVER_URL = "http://127.0.0.1:8089"

WORD_NUMS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20
}

def extract_query_constraints(
    user_text: str,
    default_radius: float = 5000.0,
    default_limit: int = 5
) -> Tuple[int, float, bool, bool]:
    """
    Extracts explicit parking count (limit) and radius from natural language.
    Defaults to 5 parking spots and 5000m (5 km) radius if not explicitly requested.
    Returns: (effective_limit, effective_radius, has_explicit_limit, has_explicit_radius)
    """
    q = user_text.lower().strip()
    limit = None
    radius = None

    # 1. Limit extraction (e.g. "10 parking spots", "8 parking stations", "top 10")
    m_count = re.search(r"\b(\d+)\s*(?:parking|spots|stations|places|locations|lots|spaces)\b", q)
    if m_count:
        limit = int(m_count.group(1))
    else:
        m_word = re.search(r"\b(" + "|".join(WORD_NUMS.keys()) + r")\s+(?:parking|spots|stations|places|locations|lots|spaces)\b", q)
        if m_word:
            limit = WORD_NUMS[m_word.group(1)]
        else:
            m_verb = re.search(r"\b(?:find|show|give|list|get|bring|bring up|display|need|want|top)\s+(?:me\s+)?(?:the\s+)?(?:top\s+)?(\d+)\b", q)
            if m_verb:
                limit = int(m_verb.group(1))

    # 2. Radius extraction
    # "within 3 km", "in 5 kms", "radius of 4 kilometers", "under 2.5 km"
    m_rad_km = re.search(r"\b(?:within|in|radius\s*(?:of)?|around|near|under|upto|up\s*to)\s*(\d+(?:\.\d+)?)\s*(?:km|kms|kilometer|kilometers|k\.m\.|k)\b", q)
    if m_rad_km:
        radius = float(m_rad_km.group(1)) * 1000.0
    else:
        # "within 800 meters", "in 500m"
        m_rad_m = re.search(r"\b(?:within|in|radius\s*(?:of)?|around|near|under|upto|up\s*to)\s*(\d+)\s*(?:m|meter|meters|mtr|mtrs)\b", q)
        if m_rad_m:
            radius = float(m_rad_m.group(1))
        else:
            # "3 km radius", "5kms radius"
            m_rad_post = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:km|kms|kilometer|kilometers)\s*(?:radius)?\b", q)
            if m_rad_post:
                radius = float(m_rad_post.group(1)) * 1000.0
            else:
                m_rad_post_m = re.search(r"\b(\d+)\s*(?:m|meter|meters)\s*radius\b", q)
                if m_rad_post_m:
                    radius = float(m_rad_post_m.group(1))

    effective_limit = max(1, min(limit if limit is not None else default_limit, 50))
    effective_radius = max(100.0, min(radius if radius is not None else default_radius, 50000.0))
    return effective_limit, effective_radius, limit is not None, radius is not None

GENERIC_LOCS = {"me", "my location", "here", "current location", "destination", "now", "us", "current"}

def extract_target_location_query(user_text: str) -> Optional[str]:
    """
    Extracts location name if user asks for parking near/in/at/around a specific place.
    e.g. "bring out 13 parking slots nearby Redhills" -> "Redhills"
         "find parking in Gummidipoondi" -> "Gummidipoondi"
         "show 5 spots near Marina Beach" -> "Marina Beach"
         "parking around T Nagar" -> "T Nagar"
         "parking at Chennai Central" -> "Chennai Central"
    """
    q = user_text.strip()
    pattern = r"\b(?:nearby|near to|near|around|in|at|close to|towards)\s+([A-Za-z0-9\s\.\-]+?)(?:\s+(?:within|in|radius|under|upto|\d+\s*km|\d+\s*m)|\.|\?|!|$)"
    m = re.search(pattern, q, re.IGNORECASE)
    if m:
        loc = m.group(1).strip()
        loc = re.sub(r"\b(?:parking|slots|spots|places|stations|locations|cars|vehicles)\b", "", loc, flags=re.IGNORECASE).strip()
        if loc and loc.lower() not in GENERIC_LOCS and len(loc) > 1:
            return loc
    return None

MCP_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_parking",
            "description": "Search offline OpenStreetMap database for parking places near GPS coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Latitude of search location"
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Longitude of search location"
                    },
                    "radius_meters": {
                        "type": "number",
                        "description": "Search radius in meters. Default is 5000 (5 km). If user specifies radius in km (e.g. 3 km), pass 3000."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of parking spots to return. Default is 5. If user specifically asks for N spots (e.g. 10), pass N."
                    },
                    "parking_type": {
                        "type": "string",
                        "enum": ["any", "surface", "underground", "multi-storey", "garage"],
                        "description": "Type of parking structure"
                    },
                    "fee_filter": {
                        "type": "string",
                        "enum": ["any", "free", "paid"],
                        "description": "Filter by fee status"
                    }
                },
                "required": ["latitude", "longitude"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "geocode_offline",
            "description": "Look up GPS coordinates of landmarks or areas offline (e.g. 'Chennai Central', 'T Nagar', 'Marina Beach').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Landmark or area name to resolve offline"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_parking_details",
            "description": "Retrieve full OpenStreetMap attributes for a specific parking spot ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "osm_id": {
                        "type": "string",
                        "description": "OSM identifier of the parking spot"
                    }
                },
                "required": ["osm_id"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are ParkVoice, a fast offline voice assistant for drivers.
You search parking using offline OpenStreetMap tools.
Rules:
1. Immediately call `search_parking`.
   - If user asks for a specific count of parking spots (e.g., "10 parking spots"), pass limit=<count>. Otherwise default limit to 5.
   - If user asks for a specific radius (e.g., "within 3 km"), pass radius_meters in meters (e.g., 3000). Otherwise default radius_meters to 5000 (5 km).
   - If a specific landmark or location is mentioned (like Marina Beach or T Nagar), use `geocode_offline` or search around that landmark.
2. In your spoken response, state the exact number of spots found and search radius. Summarize the best spots (name, distance, fee, capacity). Keep answers clear and brief for voice.
"""

class AgentOrchestrator:
    def __init__(
        self,
        llama_url: str = LLAMA_SERVER_URL,
        mcp_tools: Optional[OsmMcpTools] = None,
        speech_engine: Optional[OfflineSpeechEngine] = None
    ):
        self.llama_url = llama_url.rstrip("/")
        self.mcp = mcp_tools or OsmMcpTools()
        self.speech = speech_engine or OfflineSpeechEngine()

    async def check_llama_health(self) -> bool:
        """Check if llama.cpp server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.llama_url}/health")
                return res.status_code == 200
        except Exception:
            return False

    def execute_mcp_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        default_limit: int = 5,
        default_radius: float = 5000.0
    ) -> Tuple[Any, Dict[str, Any]]:
        """Executes a tool on the offline OpenStreetMap MCP server."""
        t0 = time.time()
        result = None
        if tool_name == "search_parking":
            lat = float(arguments.get("latitude") if arguments.get("latitude") is not None else arguments.get("lat", 13.0827))
            lon = float(arguments.get("longitude") if arguments.get("longitude") is not None else arguments.get("lon", arguments.get("lng", 80.2707)))
            radius = float(arguments.get("radius_meters") or arguments.get("radius") or default_radius)
            p_type = str(arguments.get("parking_type") or arguments.get("type", "any"))
            fee = str(arguments.get("fee_filter") or arguments.get("fee", "any"))
            limit = int(arguments.get("limit") or default_limit)
            result = self.mcp.search_parking(lat, lon, radius, p_type, fee, limit)
        elif tool_name == "geocode_offline":
            query = str(arguments.get("query") or arguments.get("location", ""))
            result = self.mcp.geocode_offline(query)
        elif tool_name == "get_parking_details":
            osm_id = str(arguments.get("osm_id", ""))
            result = self.mcp.get_parking_details(osm_id)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        elapsed = time.time() - t0
        log_entry = {
            "tool": tool_name,
            "arguments": arguments,
            "result_summary": f"Returned {len(result)} items" if isinstance(result, list) else "Success",
            "execution_time_seconds": round(elapsed, 4)
        }
        return result, log_entry

    async def process_query(
        self,
        user_text: str,
        user_lat: float = 13.0827,
        user_lon: float = 80.2707,
        radius_meters: float = 5000.0,
        synthesize_tts: bool = True
    ) -> Dict[str, Any]:
        """
        End-to-end agentic workflow:
        1. Contextualize query with user location, desired limit, and radius.
        2. Prompt Qwen 3 via llama.cpp with MCP tool definitions.
        3. Execute tool calls against offline OpenStreetMap database with exact limits/radius.
        4. Generate final spoken answer.
        5. Synthesize speech using offline Piper TTS.
        """
        start_time = time.time()
        tool_executions = []
        found_spots = []
        final_answer = ""
        timings = {}
        target_lat = user_lat
        target_lon = user_lon
        location_label = "your location"

        # Check if user explicitly specified a target location (e.g. "nearby Redhills")
        extracted_loc = extract_target_location_query(user_text)
        if extracted_loc:
            geo_match = self.mcp.geocode_offline(extracted_loc)
            if geo_match.get("found"):
                target_lat = float(geo_match["latitude"])
                target_lon = float(geo_match["longitude"])
                location_label = geo_match.get("name", extracted_loc)
                print(f"[Orchestrator] Explicit target location resolved: '{location_label}' at ({target_lat}, {target_lon})")

        # Extract explicit constraints from natural language (count & radius)
        req_limit, req_radius, has_expl_limit, has_expl_radius = extract_query_constraints(
            user_text,
            default_radius=radius_meters,
            default_limit=5
        )
        effective_limit = req_limit
        effective_radius = req_radius

        # Initial message history with exact parameters and resolved location
        radius_km = effective_radius / 1000.0
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Location: lat {target_lat:.4f}, lon {target_lon:.4f} ({location_label}). Desired spots: {effective_limit}. Search radius: {effective_radius:.0f}m ({radius_km:.1f}km). Query: \"{user_text}\""
            }
        ]

        # Check if user is asking to download an offline map or region
        lower_q = user_text.lower().strip()
        if "download" in lower_q and any(k in lower_q for k in ["map", "region", "parking", "data", "offline"]):
            place_name = lower_q
            for prefix in [
                "download offline map for", "download map for",
                "download offline parking for", "download parking for",
                "download map of", "download offline data for", "download"
            ]:
                if prefix in place_name:
                    place_name = place_name.split(prefix, 1)[1]
                    break
            place_name = place_name.replace("please", "").strip(" .!?:")
            if place_name:
                from scripts.download_osm_region import download_region_by_name
                dl_res = download_region_by_name(place_name)
                if dl_res.get("success") and dl_res.get("count", 0) > 0:
                    target_lat = dl_res.get("latitude", user_lat)
                    target_lon = dl_res.get("longitude", user_lon)
                    found_spots = self.mcp.search_parking(
                        target_lat,
                        target_lon,
                        radius_meters=effective_radius,
                        limit=effective_limit
                    )
                    final_answer = f"I downloaded {dl_res['count']} parking spots for {dl_res.get('display_name', place_name)} from OpenStreetMap mirrors into your offline database."
                elif dl_res.get("success"):
                    final_answer = f"I connected to the OpenStreetMap mirrors, but 0 parking spots were found for {place_name}."
                else:
                    final_answer = f"No map was found in mirrors for '{place_name}' ({dl_res.get('message', 'Unreachable or not found')})."

        t_llm0 = time.time()

        if not final_answer:
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    # Step 1: Tool call request
                    payload = {
                        "messages": messages,
                        "tools": MCP_TOOL_DEFINITIONS,
                        "tool_choice": "auto",
                        "max_tokens": 384,
                        "temperature": 0.1
                    }
                    
                    resp = await client.post(f"{self.llama_url}/v1/chat/completions", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    choice = data["choices"][0]
                    assistant_msg = choice["message"]

                    tool_calls = assistant_msg.get("tool_calls", [])

                    if tool_calls:
                        # Append assistant message with tool calls
                        messages.append(assistant_msg)

                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name")
                            raw_args = fn.get("arguments", "{}")
                            try:
                                fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                            except Exception:
                                fn_args = {"latitude": user_lat, "longitude": user_lon}

                            # Ensure coordinates default to target location if not provided
                            if "latitude" not in fn_args and "lat" not in fn_args:
                                fn_args["latitude"] = target_lat
                            if "longitude" not in fn_args and "lon" not in fn_args and "lng" not in fn_args:
                                fn_args["longitude"] = target_lon

                            # If user explicitly requested a location (e.g. Redhills) and model passed preset user_lat, override
                            if extracted_loc and target_lat != user_lat:
                                if abs(float(fn_args.get("latitude", 0)) - user_lat) < 0.001:
                                    fn_args["latitude"] = target_lat
                                    fn_args["longitude"] = target_lon

                            # Execute MCP Tool with effective limit and radius
                            mcp_result, trace = self.execute_mcp_tool(
                                fn_name,
                                fn_args,
                                default_limit=effective_limit,
                                default_radius=effective_radius
                            )
                            tool_executions.append(trace)

                            if fn_name == "search_parking" and isinstance(mcp_result, list):
                                found_spots = mcp_result
                                if "limit" in fn_args:
                                    try:
                                        effective_limit = int(fn_args["limit"])
                                    except Exception:
                                        pass
                                if "radius_meters" in fn_args:
                                    try:
                                        effective_radius = float(fn_args["radius_meters"])
                                    except Exception:
                                        pass
                            elif fn_name == "geocode_offline" and isinstance(mcp_result, dict) and mcp_result.get("found"):
                                target_lat = mcp_result.get("latitude", user_lat)
                                target_lon = mcp_result.get("longitude", user_lon)
                                # Auto search parking at geocoded location with exact constraints
                                geo_spots = self.mcp.search_parking(
                                    target_lat,
                                    target_lon,
                                    radius_meters=effective_radius,
                                    limit=effective_limit
                                )
                                if geo_spots:
                                    found_spots = geo_spots

                            # Format a concise summary for the LLM to keep inference fast on CPU
                            if fn_name == "search_parking" and isinstance(mcp_result, list):
                                summary_limit = min(effective_limit, 15)
                                tool_payload = [
                                    {
                                        "name": s.get("name"),
                                        "distance": s.get("distance_text"),
                                        "fee": s.get("fee"),
                                        "capacity": s.get("capacity"),
                                        "type": s.get("parking_type"),
                                        "hours": s.get("opening_hours")
                                    }
                                    for s in mcp_result[:summary_limit]
                                ]
                            else:
                                tool_payload = mcp_result

                            # Add tool result to conversation
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", "call_default"),
                                "name": fn_name,
                                "content": json.dumps(tool_payload)
                            })

                        # Step 2: Final synthesis call to Qwen3
                        payload_synthesis = {
                            "messages": messages,
                            "max_tokens": 250,
                            "temperature": 0.2
                        }
                        synth_resp = await client.post(f"{self.llama_url}/v1/chat/completions", json=payload_synthesis)
                        synth_resp.raise_for_status()
                        synth_data = synth_resp.json()
                        synth_choice = synth_data["choices"][0]["message"]
                        final_answer = synth_choice.get("content", "").strip()

                        # Fallback if content is empty but reasoning is present
                        if not final_answer and "reasoning_content" in synth_choice:
                            final_answer = synth_choice["reasoning_content"][-250:].strip()
                    else:
                        # Assistant answered directly
                        final_answer = assistant_msg.get("content", "").strip()

            except Exception as e:
                print(f"[Orchestrator] Error communicating with llama.cpp: {e}")
                final_answer = ""

        # Clean any stray <think> tags from answer
        if final_answer:
            final_answer = re.sub(r"<think>.*?</think>", "", final_answer, flags=re.DOTALL).strip()

        timings["llm_total"] = round(time.time() - t_llm0, 2)

        # Fallback safeguard: if LLM didn't return spots or failed, perform direct offline OSM search
        if not found_spots:
            # Attempt to resolve any specific landmark or region named in user_text
            geo_match = self.mcp.geocode_offline(user_text)
            if geo_match.get("found"):
                target_lat = geo_match["latitude"]
                target_lon = geo_match["longitude"]
                location_label = geo_match.get("name", "destination")
            else:
                location_label = "your location"

            direct_spots = self.mcp.search_parking(
                target_lat,
                target_lon,
                radius_meters=effective_radius,
                limit=effective_limit
            )
            if direct_spots:
                found_spots = direct_spots
                best = direct_spots[0]
                rad_str = f"{effective_radius/1000:.1f} km" if effective_radius >= 1000 else f"{int(effective_radius)}m"
                final_answer = (
                    f"I found {len(direct_spots)} parking spots near {location_label} within {rad_str}. "
                    f"The closest is {best['name']}, {best['distance_text']} away, "
                    f"with {best['capacity']} spaces and {best['fee']} fee."
                )

        if not final_answer and found_spots:
            best = found_spots[0]
            rad_str = f"{effective_radius/1000:.1f} km" if effective_radius >= 1000 else f"{int(effective_radius)}m"
            final_answer = (
                f"I found {len(found_spots)} parking spots near {location_label} within {rad_str}. "
                f"The nearest is {best['name']}, {best['distance_text']} away. "
                f"Fee is {best['fee']}."
            )
        elif not final_answer:
            rad_str = f"{effective_radius/1000:.1f} km" if effective_radius >= 1000 else f"{int(effective_radius)}m"
            final_answer = f"No parking spots found near {location_label} within {rad_str} in the offline map."

        # Step 3: Text-to-Speech synthesis
        audio_b64 = None
        t_tts0 = time.time()
        if synthesize_tts and final_answer:
            try:
                audio_b64, t_tts = self.speech.synthesize_speech_base64(final_answer)
                timings["tts"] = round(t_tts, 2)
            except Exception as e:
                print(f"[Orchestrator] TTS synthesis error: {e}")
                timings["tts"] = 0.0

        timings["total"] = round(time.time() - start_time, 2)

        return {
            "answer": final_answer,
            "user_query": user_text,
            "user_location": {"latitude": user_lat, "longitude": user_lon},
            "target_location": {"latitude": target_lat, "longitude": target_lon, "name": location_label},
            "effective_limit": effective_limit,
            "effective_radius": effective_radius,
            "radius_meters": effective_radius,
            "parking_spots": found_spots,
            "tool_executions": tool_executions,
            "audio_base64": audio_b64,
            "timings": timings
        }
