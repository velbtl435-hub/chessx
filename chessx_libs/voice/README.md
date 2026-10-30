# chessx_libs.voice
Natural text-to-speech + offline speech-to-text for ChessX in **en** (default), **pt** (pt-BR) and **ja**,
with a robot mode. Every dependency is optional and imported lazily; without them the API returns
`"noop"` / `None` and never raises.

- **Origin:** written for ChessX v0.6. **License:** same as the repo; pyttsx3 (MPL-2.0), Vosk (Apache-2.0),
  Piper (MIT), edge-tts (LGPL-3.0), eSpeak NG (GPL-3.0) keep their own licenses.

## TTS (`tts.py`) — natural first, robotic eSpeak last
1. **Piper** (offline neural) if `piper` is on PATH and a voice model exists: `CHESSX_PIPER_MODEL_PT=/path/pt_BR-faber-medium.onnx`
   or `~/.cache/chessx/piper/pt_BR-*.onnx` (`en_US-*`, `ja_JP-*`).
2. **edge-tts** (online neural: Aria / Francisca / Nanami) if `pip install edge-tts` + ffmpeg. Disable with `CHESSX_TTS_OFFLINE=1`.
3. **pyttsx3** with the best installed voice for the language (`pick_voice`): premium/neural/enhanced SAPI5 &
   NSSpeechSynthesizer voices > MBROLA (`mb-br1`, `mb-us1`) > plain eSpeak.
4. OS binary: `say`, `espeak-ng`/`espeak` (MBROLA or `+f3` variant, 150 wpm), `spd-say`, PowerShell. Then noop.

Config: `configure(rate=165, volume=1.0, backend="piper", offline=False, robot=False)` or env
`CHESSX_TTS_RATE`, `CHESSX_TTS_VOLUME`, `CHESSX_TTS_BACKEND`, `CHESSX_TTS_ROBOT`.
On Linux, `apt install espeak-ng mbrola mbrola-br1 mbrola-us1` noticeably improves pyttsx3.

## STT (`stt.py`) — Vosk
Per-language models (never falls back to another language's model): `vosk-model-small-en-us-0.15`,
`vosk-model-small-pt-0.3`, `vosk-model-small-ja-0.22` in `CHESSX_MODEL_DIR` (default `~/.cache/chessx`), or
`CHESSX_VOSK_MODEL_PT=/path` (`CHESSX_VOSK_MODEL` = any language). `download_model("pt")` fetches it.
Audio is converted to 16 kHz mono s16 (ffmpeg, numpy fallback); output is UTF-8 with accents.
`transcribe_file(path, strict=True)` raises `ModelNotFound` with a hint instead of returning `None`.

## Language
`lang=None` everywhere follows: `voice.set_lang("pt")` > the app's i18n `Translator` (bound in `chessx.py` via
`voice.bind_translator(self.t)`, so the `lang pt` command switches voice too) > `CHESSX_LANG` > `en`.

## Robot mode (`robot.py`)
numpy chain on the rendered WAV: pitch down → ring modulation (55 Hz) → metallic comb → bitcrush. Works with
any backend. Toggle: `voice.robot_mode(True)`, `speak(text, robot=True)`, `CHESSX_TTS_ROBOT=1`, or CLI `--robot`.
Without numpy, live eSpeak uses a monotone `+klatt3` voice.

## CLI
```
python -m chessx_libs.voice "Xeque-mate!" --lang pt [--robot] [-o out.wav] [--rate 150]
python -m chessx_libs.voice --voices --lang ja
python -m chessx_libs.voice --transcribe jogada.wav --lang pt
```

## Tests
`python -m pytest chessx_libs/voice/tests` — engines, Vosk and audio are mocked; runs headless.
