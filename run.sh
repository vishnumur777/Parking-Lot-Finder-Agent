#!/usr/bin/env bash
# ==============================================================================
# ParkVoice Offline PWA - Master Launcher
# Launches:
# 1. llama.cpp server hosting Qwen 3 (1.7B GGUF) on port 8089
# 2. FastAPI backend & PWA server on port 8080
# 100% Offline with zero external dependencies.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LLAMA_BIN="/home/varun/.llama-app/llama"
DEFAULT_MODEL="/home/varun/.cache/huggingface/hub/models--unsloth--Qwen3-1.7B-GGUF/snapshots/d7f544eead698dbd1f15126ef60b45a1e1933222/Qwen3-1.7B-Q4_0.gguf"
MODEL_PATH="${1:-$DEFAULT_MODEL}"
LLAMA_PORT=8089
APP_PORT=8001

echo "=============================================================="
echo "      ParkVoice - 100% Offline Voice OSM Parking PWA          "
echo "=============================================================="
echo "• LLM: Qwen 3 (1.7B Q4_0 GGUF via llama.cpp)"
echo "• Model Path: $MODEL_PATH"
echo "• STT: Faster-Whisper (base.en with VAD offline)"
echo "• MCP: OpenStreetMap MCP Server (100% Offline SQLite)"
echo "• TTS: Piper TTS (en_US-lessac-medium offline)"
echo "• PWA UI: http://127.0.0.1:$APP_PORT"
echo "=============================================================="

# Check LLAMA binary
if [ ! -f "$LLAMA_BIN" ]; then
    echo "ERROR: llama binary not found at $LLAMA_BIN"
    exit 1
fi

# Check model
if [ ! -f "$MODEL_PATH" ]; then
    echo "ERROR: Model GGUF not found at $MODEL_PATH"
    exit 1
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down offline services..."
    if [ -n "$LLAMA_PID" ]; then
        kill "$LLAMA_PID" 2>/dev/null || true
    fi
    if [ -n "$SERVER_PID" ]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    echo "Done. Goodbye!"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Kill any existing server on ports
fuser -k $LLAMA_PORT/tcp 2>/dev/null || true
fuser -k $APP_PORT/tcp 2>/dev/null || true

# 1. Start llama.cpp server
echo "Starting llama.cpp server on port $LLAMA_PORT..."
"$LLAMA_BIN" serve \
    -m "$MODEL_PATH" \
    --port "$LLAMA_PORT" \
    -c 4096 \
    -n 384 \
    --threads 4 \
    --reasoning off \
    --reasoning-budget 0 > /tmp/llama_server_parkvoice.log 2>&1 &
LLAMA_PID=$!

echo "Waiting for llama.cpp server to initialize..."
for i in {1..30}; do
    if curl -s "http://127.0.0.1:$LLAMA_PORT/health" | grep -q "ok"; then
        echo "✓ llama.cpp server is ready!"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "WARNING: llama.cpp took longer than expected to report healthy, continuing..."
    fi
done

# 2. Start FastAPI PWA Server
echo "Starting ParkVoice FastAPI backend on http://127.0.0.1:$APP_PORT..."
.venv/bin/python server.py &
SERVER_PID=$!

# Wait for FastAPI server to start
sleep 2
echo "✓ ParkVoice PWA is live at http://127.0.0.1:$APP_PORT"
echo "Press Ctrl+C to stop all offline services."

wait $SERVER_PID
