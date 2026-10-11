"""
Offline Speech Engine
Handles 100% offline Speech-to-Text (STT) via Faster-Whisper
and Text-to-Speech (TTS) via Piper TTS.
"""

import os
import io
import time
import wave
import base64
from typing import Optional, Tuple
from faster_whisper import WhisperModel
import piper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WHISPER_DIR = os.path.join(BASE_DIR, "models", "whisper")
TTS_MODEL_PATH = os.path.join(BASE_DIR, "models", "tts", "en_US-lessac-medium.onnx")
TTS_CONFIG_PATH = os.path.join(BASE_DIR, "models", "tts", "en_US-lessac-medium.onnx.json")

DEFAULT_WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base.en")

class OfflineSpeechEngine:
    def __init__(
        self,
        whisper_model_size: str = DEFAULT_WHISPER_MODEL,
        whisper_dir: str = WHISPER_DIR,
        tts_model_path: str = TTS_MODEL_PATH,
        tts_config_path: str = TTS_CONFIG_PATH
    ):
        self.whisper_dir = whisper_dir
        self.whisper_model_size = whisper_model_size
        self.tts_model_path = tts_model_path
        self.tts_config_path = tts_config_path

        self._whisper: Optional[WhisperModel] = None
        self._piper_voice: Optional[piper.PiperVoice] = None

    def get_whisper(self) -> WhisperModel:
        if self._whisper is None:
            print(f"[STT] Loading offline Whisper model ({self.whisper_model_size})...")
            try:
                self._whisper = WhisperModel(
                    self.whisper_model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=self.whisper_dir,
                    local_files_only=True
                )
            except Exception as e:
                print(f"[STT] Could not load '{self.whisper_model_size}' offline ({e}). Checking fallbacks...")
                fallback = "tiny.en" if "tiny.en" in os.listdir(self.whisper_dir) else "base.en"
                self._whisper = WhisperModel(
                    fallback,
                    device="cpu",
                    compute_type="int8",
                    download_root=self.whisper_dir,
                    local_files_only=True
                )
                self.whisper_model_size = fallback
            print(f"[STT] Offline Whisper model loaded: {self.whisper_model_size}")
        return self._whisper

    def get_piper(self) -> piper.PiperVoice:
        if self._piper_voice is None:
            print("[TTS] Loading offline Piper voice model...")
            if not os.path.exists(self.tts_model_path):
                raise FileNotFoundError(f"TTS model not found at {self.tts_model_path}")
            self._piper_voice = piper.PiperVoice.load(
                self.tts_model_path,
                self.tts_config_path
            )
            print("[TTS] Offline Piper voice model loaded.")
        return self._piper_voice

    def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        language: Optional[str] = "en",
        initial_prompt: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Transcribe raw audio bytes (WebM, WAV, MP3, OGG) to text.
        Applies Silero VAD to eliminate background noise hallucinations,
        primes with domain vocabulary, and uses beam search for high accuracy.
        Returns: (transcribed_text, elapsed_time_seconds)
        """
        t0 = time.time()
        whisper = self.get_whisper()
        audio_stream = io.BytesIO(audio_bytes)
        
        prompt = initial_prompt or (
            "Parking assistant. Find parking, car parking, nearest parking spot, "
            "free parking, underground parking, multi-storey garage. "
            "Locations: Chennai Central, T Nagar, Marina Beach, Anna Nagar, Koyambedu, Thiruvallur."
        )

        try:
            segments, info = whisper.transcribe(
                audio_stream,
                beam_size=2,
                best_of=2,
                language=language,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400),
                initial_prompt=prompt,
                condition_on_previous_text=False
            )
            text_parts = [s.text.strip() for s in segments]
            transcription = " ".join(text_parts).strip()
        except Exception as e:
            print(f"[STT] Transcription error: {e}")
            transcription = ""

        elapsed = time.time() - t0
        return transcription, elapsed

    def synthesize_speech_wav(self, text: str) -> Tuple[bytes, float]:
        """
        Synthesize text into WAV audio bytes using Piper TTS.
        Returns: (wav_bytes, elapsed_time_seconds)
        """
        t0 = time.time()
        # Clean text for smoother speech
        cleaned_text = text.replace("*", "").replace("#", "").replace("`", "")
        if not cleaned_text.strip():
            cleaned_text = "I have no response."

        voice = self.get_piper()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(voice.config.sample_rate)
            for chunk in voice.synthesize(cleaned_text):
                wav_file.writeframes(chunk.audio_int16_bytes)
                
        wav_bytes = buf.getvalue()
        elapsed = time.time() - t0
        return wav_bytes, elapsed

    def synthesize_speech_base64(self, text: str) -> Tuple[str, float]:
        """
        Synthesize text into a Base64 data URI (data:audio/wav;base64,...)
        suitable for direct web audio playback.
        """
        wav_bytes, elapsed = self.synthesize_speech_wav(text)
        b64 = base64.b64encode(wav_bytes).decode("ascii")
        return f"data:audio/wav;base64,{b64}", elapsed

if __name__ == "__main__":
    engine = OfflineSpeechEngine()
    print("Testing offline TTS...")
    wav, t_tts = engine.synthesize_speech_wav("Finding nearest parking in OpenStreetMap offline.")
    print(f"Synthesized {len(wav)} bytes in {t_tts:.2f}s")
    
    print("Testing offline STT with synthesized audio...")
    text, t_stt = engine.transcribe_audio_bytes(wav)
    print(f"Transcribed '{text}' in {t_stt:.2f}s")
