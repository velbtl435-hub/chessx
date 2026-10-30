"""Speech-to-text. Order: vosk (offline, optional) -> SpeechRecognition (optional) -> noop (returns None).

Vosk models are NOT shipped in the repo. Point CHESSX_VOSK_MODEL at a model folder, or unzip models into
~/.cache/chessx (e.g. vosk-model-small-pt-0.3, vosk-model-small-en-us-0.15) and they are found by language.
"""
import glob, json, os, shutil, subprocess, tempfile, wave

try:
    import vosk  # optional
    vosk.SetLogLevel(-1)
except Exception:
    vosk = None
try:
    import speech_recognition as sr  # optional
except Exception:
    sr = None

STT_BACKEND = "vosk" if vosk else ("speech_recognition" if sr else "noop")
MODEL_DIR = os.environ.get("CHESSX_MODEL_DIR", os.path.expanduser("~/.cache/chessx"))
_MODELS = {}


def find_model(lang: str = "en"):
    """Return a vosk model folder for a language ('en', 'pt', ...), or None."""
    env = os.environ.get("CHESSX_VOSK_MODEL")
    if env and os.path.isdir(env):
        return env
    code = lang.split("-")[0].lower()
    for pat in ("vosk-model-small-%s*" % code, "vosk-model-%s*" % code, "vosk-model-small-*"):
        hits = sorted(d for d in glob.glob(os.path.join(MODEL_DIR, pat)) if os.path.isdir(d))
        if hits:
            return hits[0]
    return None


def _to_16k_mono(path):
    """Vosk wants 16-bit mono PCM. Convert with ffmpeg when needed; returns (path, is_temp)."""
    try:
        with wave.open(path, "rb") as w:
            if w.getnchannels() == 1 and w.getsampwidth() == 2:
                return path, False
    except Exception:
        pass
    if not shutil.which("ffmpeg"):
        return path, False
    out = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ar", "16000", "-ac", "1", out],
                   timeout=120, capture_output=True)
    return (out, True) if os.path.isfile(out) else (path, False)


def transcribe_file(path: str, model_path: str = None, lang: str = "en-US"):
    """Transcribe an audio file. Returns text, or None when no backend/model is available."""
    if not os.path.isfile(path):
        return None
    model_path = model_path or (find_model(lang) if vosk else None)
    if vosk and model_path:
        src, tmp = _to_16k_mono(path)
        try:
            if model_path not in _MODELS:
                _MODELS[model_path] = vosk.Model(model_path)
            with wave.open(src, "rb") as wf:
                rec = vosk.KaldiRecognizer(_MODELS[model_path], wf.getframerate())
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    rec.AcceptWaveform(data)
            return json.loads(rec.FinalResult()).get("text", "")
        except Exception:
            return None
        finally:
            if tmp:
                os.remove(src)
    if sr:
        try:
            r = sr.Recognizer()
            with sr.AudioFile(path) as s:
                audio = r.record(s)
            return r.recognize_sphinx(audio)
        except Exception:
            return None
    return None


def listen(timeout: float = 5.0, lang: str = "en-US"):
    """Capture one phrase from the microphone. Returns None (silently) if unavailable."""
    if not sr:
        return None
    try:
        r = sr.Recognizer()
        with sr.Microphone() as mic:
            audio = r.listen(mic, timeout=timeout)
        return r.recognize_google(audio, language=lang)
    except Exception:
        return None
