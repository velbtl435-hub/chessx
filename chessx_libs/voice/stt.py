"""Speech-to-text. Order: vosk (offline, optional) -> SpeechRecognition (optional) -> noop (returns None).

Vosk models are NOT shipped. Point CHESSX_VOSK_MODEL (or CHESSX_VOSK_MODEL_<LANG>, e.g. CHESSX_VOSK_MODEL_PT)
at a model folder, or unzip models into CHESSX_MODEL_DIR (default ~/.cache/chessx). `download_model(lang)`
fetches the official small model. Imports are lazy so ChessX works without vosk installed.
"""
import glob, json, os, shutil, subprocess, tempfile, wave

MODEL_DIR = os.environ.get("CHESSX_MODEL_DIR", os.path.expanduser("~/.cache/chessx"))
MODEL_URL = "https://alphacephei.com/vosk/models/%s.zip"
# Official Vosk model names per language (small first, then large).
VOSK_MODELS = {
    "en": ("vosk-model-small-en-us-0.15", "vosk-model-en-us-0.22"),
    "pt": ("vosk-model-small-pt-0.3", "vosk-model-pt-fb-v0.1.1-20220516_2113"),
    "ja": ("vosk-model-small-ja-0.22", "vosk-model-ja-0.22"),
}
ALIASES = {"pt-br": "pt", "pt_br": "pt", "en-us": "en", "en_us": "en", "jp": "ja", "ja-jp": "ja"}
SAMPLE_RATE = 16000
_MODELS = {}


class ModelNotFound(RuntimeError):
    """No Vosk model for the requested language."""


def norm_lang(lang="en"):
    lang = (lang or "en").lower()
    lang = ALIASES.get(lang, lang)
    return lang.split("-")[0].split("_")[0]


def _vosk():
    try:
        import vosk
        vosk.SetLogLevel(-1)
        return vosk
    except Exception:
        return None


def _sr():
    try:
        import speech_recognition as sr
        return sr
    except Exception:
        return None


def _backend():
    return "vosk" if _vosk() else ("speech_recognition" if _sr() else "noop")


STT_BACKEND = _backend()


def find_model(lang: str = "en"):
    """Return a vosk model folder for a language ('en', 'pt', 'ja'), or None. Never picks another language."""
    code = norm_lang(lang)
    for env in ("CHESSX_VOSK_MODEL_" + code.upper(), "CHESSX_VOSK_MODEL"):
        p = os.environ.get(env)
        if p and os.path.isdir(p):
            return p
    for name in VOSK_MODELS.get(code, ()):
        p = os.path.join(MODEL_DIR, name)
        if os.path.isdir(p):
            return p
    for pat in ("vosk-model-small-%s*" % code, "vosk-model-%s*" % code):
        hits = sorted(d for d in glob.glob(os.path.join(MODEL_DIR, pat)) if os.path.isdir(d))
        if hits:
            return hits[0]
    return None


def download_model(lang: str = "en", dest: str = None):
    """Download + unzip the small official model for `lang`. Returns its path or None on failure."""
    import urllib.request, zipfile
    code = norm_lang(lang)
    if code not in VOSK_MODELS:
        return None
    name, dest = VOSK_MODELS[code][0], dest or MODEL_DIR
    os.makedirs(dest, exist_ok=True)
    target = os.path.join(dest, name)
    if os.path.isdir(target):
        return target
    tmp = tempfile.mktemp(suffix=".zip")
    try:
        urllib.request.urlretrieve(MODEL_URL % name, tmp)
        with zipfile.ZipFile(tmp) as z:
            z.extractall(dest)
        return target if os.path.isdir(target) else None
    except Exception:
        return None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _is_16k_mono(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == SAMPLE_RATE \
                and w.getcomptype() == "NONE"
    except Exception:
        return False


def _to_16k_mono(path):
    """Convert to 16 kHz / mono / 16-bit PCM WAV (ffmpeg, else numpy for plain WAVs). Returns (path, is_temp)."""
    if _is_16k_mono(path):
        return path, False
    out = tempfile.mktemp(suffix=".wav")
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ar", str(SAMPLE_RATE), "-ac", "1",
                        "-sample_fmt", "s16", out], timeout=120, capture_output=True)
        if os.path.isfile(out):
            return out, True
    try:  # pure numpy fallback (PCM WAV only)
        import numpy as np
        with wave.open(path, "rb") as w:
            ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
        dt = {1: np.uint8, 2: np.int16, 4: np.int32}[sw]
        a = np.frombuffer(raw, dtype=dt).astype(np.float64)
        if sw == 1:
            a = (a - 128) * 256
        elif sw == 4:
            a = a / 65536
        a = a.reshape(-1, ch).mean(axis=1)
        if sr != SAMPLE_RATE and len(a):
            m = int(len(a) * SAMPLE_RATE / sr)
            a = np.interp(np.linspace(0, len(a) - 1, m), np.arange(len(a)), a)
        with wave.open(out, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
            w.writeframes(np.clip(a, -32768, 32767).astype("<i2").tobytes())
        return out, True
    except Exception:
        return path, False


def transcribe_file(path: str, model_path: str = None, lang: str = None, strict: bool = False):
    """Transcribe an audio file to UTF-8 text (accents kept, e.g. 'cavalo para é cinco').

    Returns None when no backend/model is available; with strict=True raises ModelNotFound instead.
    """
    from .lang import current_lang
    lang = current_lang(lang)
    if not os.path.isfile(path):
        return None
    vosk = _vosk()
    model_path = model_path or (find_model(lang) if vosk else None)
    if vosk and not model_path and strict:
        raise ModelNotFound("no Vosk model for %r: run voice.stt.download_model(%r) or set CHESSX_VOSK_MODEL_%s"
                            % (norm_lang(lang), norm_lang(lang), norm_lang(lang).upper()))
    if vosk and model_path:
        src, tmp = _to_16k_mono(path)
        try:
            if model_path not in _MODELS:
                _MODELS[model_path] = vosk.Model(model_path)
            with wave.open(src, "rb") as wf:
                rec = vosk.KaldiRecognizer(_MODELS[model_path], wf.getframerate())
                parts = []
                while True:
                    data = wf.readframes(4000)
                    if not data:
                        break
                    if rec.AcceptWaveform(data):
                        parts.append(json.loads(rec.Result()).get("text", ""))
                parts.append(json.loads(rec.FinalResult()).get("text", ""))
            text = " ".join(p for p in parts if p)
            return text.encode("utf-8", "replace").decode("utf-8")
        except Exception:
            if strict:
                raise
            return None
        finally:
            if tmp and os.path.exists(src):
                os.remove(src)
    sr = _sr()
    if sr:
        try:
            r = sr.Recognizer()
            with sr.AudioFile(path) as s:
                audio = r.record(s)
            return r.recognize_sphinx(audio)
        except Exception:
            return None
    return None


GOOGLE_LANG = {"en": "en-US", "pt": "pt-BR", "ja": "ja-JP"}


def listen(timeout: float = 5.0, lang: str = None):
    """Capture one phrase from the microphone. Returns None (silently) if unavailable."""
    from .lang import current_lang
    lang = current_lang(lang)
    sr = _sr()
    if not sr:
        return None
    try:
        r = sr.Recognizer()
        with sr.Microphone() as mic:
            audio = r.listen(mic, timeout=timeout)
        return r.recognize_google(audio, language=GOOGLE_LANG.get(norm_lang(lang), lang))
    except Exception:
        return None
