#!/usr/bin/env bash
# ==============================================================================
# Setup Offline Voice Models for ParkVoice
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TTS_DIR="$SCRIPT_DIR/models/tts"
mkdir -p "$TTS_DIR"

echo "Checking Piper TTS voice models..."
if [ ! -f "$TTS_DIR/en_US-lessac-medium.onnx" ]; then
    echo "Downloading Piper en_US-lessac-medium neural ONNX model..."
    curl -L -o "$TTS_DIR/en_US-lessac-medium.onnx" \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
    curl -L -o "$TTS_DIR/en_US-lessac-medium.onnx.json" \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
    echo "✓ Piper TTS model ready in $TTS_DIR"
else
    echo "✓ Piper TTS model already present."
fi

echo "Note: Faster-Whisper automatically loads and caches its model in models/whisper on first launch."
