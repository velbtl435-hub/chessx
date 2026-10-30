"""Voice: natural TTS (Piper/edge-tts/pyttsx3/OS) + Vosk STT, en/pt/ja, silent noop fallback."""
from .tts import speak, save_to_file, available_backends, list_voices, pick_voice, configure, robot_mode, TTS_BACKEND
from .stt import listen, transcribe_file, find_model, download_model, ModelNotFound, STT_BACKEND
from .lang import set_lang, current_lang, bind_translator, SUPPORTED
__all__ = ["speak", "save_to_file", "available_backends", "list_voices", "pick_voice", "configure", "robot_mode", "TTS_BACKEND",
           "listen", "transcribe_file", "find_model", "download_model", "ModelNotFound", "STT_BACKEND",
           "set_lang", "current_lang", "bind_translator", "SUPPORTED"]
