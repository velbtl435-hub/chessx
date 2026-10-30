"""Minimal voice: TTS + STT with silent/noop fallback."""
from .tts import speak, available_backends, TTS_BACKEND
from .stt import listen, transcribe_file, STT_BACKEND
__all__ = ["speak", "available_backends", "TTS_BACKEND", "listen", "transcribe_file", "STT_BACKEND"]
