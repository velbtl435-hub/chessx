"""Minimal voice: TTS + STT with silent/noop fallback."""
from .tts import speak, save_to_file, available_backends, TTS_BACKEND
from .stt import listen, transcribe_file, find_model, STT_BACKEND
__all__ = ["speak", "save_to_file", "available_backends", "TTS_BACKEND",
           "listen", "transcribe_file", "find_model", "STT_BACKEND"]
