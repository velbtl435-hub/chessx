# chessx_libs
The library packages behind ChessX v0.6. The root `chessx.py` wires them together, and `python3 chessx.py --selftest` smoke-tests each one.

- **Origin:** split out of the single-file chessx.py v0.5 (kept as `chessx_v05_legacy.py`) and extended.
- **License:** same as the ChessX repository.
- **Packages:** chess_ai, i18n, interface, crypto, search, media, reversing, voice, windows, sounds, detective, bases, scheduler, audit. Each has its own README covering origin, license and what was adapted.
- **Dependencies:** Python 3 stdlib only. Optional extras are detected automatically: ddgs, capstone, pyttsx3, vosk, SpeechRecognition, argon2-cffi.
