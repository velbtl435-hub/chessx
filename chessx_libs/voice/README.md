# chessx_libs.voice
Origin: written for ChessX (2026). License: MIT.
TTS: pyttsx3 (optional) -> OS binary (espeak-ng, espeak, say, spd-say, PowerShell System.Speech) -> silent noop.
STT: vosk (optional, offline, needs a model dir) -> SpeechRecognition (optional; `listen()` uses Google web STT,
`transcribe_file()` uses PocketSphinx) -> noop returning None.
No dependency is required; all are auto-detected. Adapted: nothing copied, only public APIs used.
