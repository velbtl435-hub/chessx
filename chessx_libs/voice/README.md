# chessx_libs.voice
Minimal text-to-speech and speech-to-text with a silent noop fallback. It never raises.

- **Origin:** written for ChessX v0.6.
- **License:** same as the ChessX repository. pyttsx3 (MPL-2.0), Vosk (Apache-2.0) and eSpeak NG (GPL-3.0) keep their own licenses.
- **Adapted:**
  - TTS tries pyttsx3, then the espeak-ng/espeak/say/spd-say/PowerShell binary, then noop. If `pyttsx3.init()` fails
    (e.g. eSpeak missing), the next backend is used.
  - `save_to_file()` renders a WAV with no audio hardware.
  - STT tries Vosk (offline), then SpeechRecognition, then None. Models are found automatically in `~/.cache/chessx`
    (or via `CHESSX_VOSK_MODEL`), and audio is converted to 16 kHz mono with ffmpeg.
- **API:** `speak(text, lang)`, `save_to_file(text, path, lang)`, `available_backends()`, `TTS_BACKEND`,
  `transcribe_file(path, model_path=None, lang)`, `find_model(lang)`, `listen()`, `STT_BACKEND`.
- **Note:** synthetic eSpeak audio transcribes poorly with the small models (best on en-us). Use real speech for accuracy.
