"""Text-to-speech with natural voices first, robotic eSpeak last.

Order: Piper (offline neural, optional) -> edge-tts (online neural, optional) -> pyttsx3 with the best
installed voice for the language (SAPI5/NSSpeechSynthesizer/espeak-ng+mbrola) -> OS binary
(say/PowerShell/espeak-ng/espeak/spd-say) -> noop. Never raises; every import is lazy.

Config: configure(rate=, volume=, backend=) or env CHESSX_TTS_RATE (wpm, default 165),
CHESSX_TTS_VOLUME (0..1), CHESSX_TTS_BACKEND (force one), CHESSX_PIPER_MODEL[_EN|_PT|_JA] (.onnx path),
CHESSX_TTS_OFFLINE=1 (skip edge-tts).
"""
import glob, os, shutil, subprocess, sys, tempfile

LANG_VOICE = {"en": "en-us", "pt": "pt-br", "ja": "ja"}
# MBROLA diphone voices sound far less robotic than formant eSpeak; used when installed.
MBROLA = {"en": ("mb-us1", "us1"), "pt": ("mb-br1", "br1"), "ja": ()}
EDGE_VOICES = {"en": "en-US-AriaNeural", "pt": "pt-BR-FranciscaNeural", "ja": "ja-JP-NanamiNeural"}
PIPER_PREFIX = {"en": "en_US", "pt": "pt_BR", "ja": "ja_JP"}
# substrings that identify natural/high quality system voices, per language (lowercase)
NATURAL_HINTS = ("neural", "natural", "enhanced", "premium", "online")  # mbrola ("mb-") scores lower
NATURAL_NAMES = {
    "en": ("aria", "jenny", "zira", "samantha", "alex", "ava", "daniel", "karen", "moira"),
    "pt": ("francisca", "maria", "luciana", "felipe", "joana", "daniel", "antonio", "br1", "br3"),
    "ja": ("nanami", "haruka", "ayumi", "kyoko", "otoya", "sayaka", "ichiro"),
}
LANG_TAGS = {"en": ("en", "english"), "pt": ("pt", "portug", "brazil"), "ja": ("ja", "japan", "日本")}
_BINARIES = ("say", "espeak-ng", "espeak", "spd-say")

CONFIG = {
    "rate": int(os.environ.get("CHESSX_TTS_RATE", "165")),
    "volume": float(os.environ.get("CHESSX_TTS_VOLUME", "1.0")),
    "backend": os.environ.get("CHESSX_TTS_BACKEND") or None,
    "offline": os.environ.get("CHESSX_TTS_OFFLINE", "") == "1",
}


def configure(**kw):
    """Update rate (wpm), volume (0..1), backend (force), offline. Returns the config."""
    for k, v in kw.items():
        if k not in CONFIG:
            raise KeyError(k)
        CONFIG[k] = v
    CONFIG["volume"] = max(0.0, min(1.0, float(CONFIG["volume"])))
    return dict(CONFIG)


def _code(lang):
    lang = (lang or "en").lower().replace("_", "-")
    return {"jp": "ja", "pt-br": "pt"}.get(lang, lang).split("-")[0]


def _espeak_voice(lang):
    code = _code(lang)
    m = MBROLA.get(code, ())
    if m:
        dirs = ("/usr/share/mbrola", "/usr/lib/x86_64-linux-gnu/espeak-ng-data/voices/mb")
        if any(os.path.exists(os.path.join(d, m[1])) for d in dirs):
            return m[0]
    # '+f3' variant + slower rate is noticeably smoother than the default male formant voice
    return LANG_VOICE.get(code, "en-us") + "+f3"


# ---------- pyttsx3 ----------
def _pyttsx3_engine():
    try:
        import pyttsx3
        return pyttsx3.init()
    except Exception:  # not installed, or RuntimeError: eSpeak not installed
        return None


def _voice_langs(v):
    out = []
    for l in getattr(v, "languages", None) or []:
        if isinstance(l, bytes):
            l = l.decode("utf-8", "ignore").lstrip("\x05")
        out.append(str(l).lower())
    return out


def score_voice(v, lang):
    """Higher is better; <= 0 means the voice does not speak `lang`."""
    code = _code(lang)
    text = " ".join([str(getattr(v, "id", "")), str(getattr(v, "name", ""))] + _voice_langs(v)).lower()
    langs = _voice_langs(v)
    s = 0
    if any(l.replace("_", "-").split("-")[0] == code for l in langs):
        s += 10
    elif any(t in text for t in LANG_TAGS.get(code, ())[1:]) or ("\\" + code) in text or ("/" + code) in text:
        s += 6
    if s <= 0:
        return 0
    if code == "pt" and ("br" in text or "brazil" in text):
        s += 2
    s += 8 * any(h in text for h in NATURAL_HINTS)
    s += 5 * ("mb-" in text or "mbrola" in text)
    s += 4 * any(n in text for n in NATURAL_NAMES.get(code, ()))
    if "espeak" in text and "mb-" not in text:
        s -= 2
    return s


def pick_voice(voices, lang="en"):
    """Return the best voice object for `lang` from pyttsx3 voices, or None."""
    best = max(voices or [], key=lambda v: score_voice(v, lang), default=None)
    return best if best is not None and score_voice(best, lang) > 0 else None


def list_voices(lang=None):
    eng = _pyttsx3_engine()
    if not eng:
        return []
    vs = eng.getProperty("voices") or []
    if lang:
        vs = sorted((v for v in vs if score_voice(v, lang) > 0), key=lambda v: -score_voice(v, lang))
    return [{"id": v.id, "name": v.name, "languages": _voice_langs(v)} for v in vs]


def _configured_engine(lang):
    eng = _pyttsx3_engine()
    if not eng:
        return None
    try:
        v = pick_voice(eng.getProperty("voices"), lang)
        if v is not None:
            eng.setProperty("voice", v.id)
        eng.setProperty("rate", int(CONFIG["rate"]))
        eng.setProperty("volume", float(CONFIG["volume"]))
    except Exception:
        pass
    return eng


# ---------- Piper / edge-tts ----------
def piper_model(lang="en"):
    code = _code(lang)
    for env in ("CHESSX_PIPER_MODEL_" + code.upper(), "CHESSX_PIPER_MODEL"):
        p = os.environ.get(env)
        if p and os.path.isfile(p):
            return p
    d = os.path.join(os.environ.get("CHESSX_MODEL_DIR", os.path.expanduser("~/.cache/chessx")), "piper")
    hits = sorted(glob.glob(os.path.join(d, PIPER_PREFIX.get(code, code) + "*.onnx")))
    return hits[0] if hits else None


def _piper_bin():
    return shutil.which("piper") or shutil.which("piper-tts")


def _edge_ok():
    if CONFIG["offline"]:
        return False
    try:
        import edge_tts  # noqa: F401
        return bool(shutil.which("ffmpeg"))
    except Exception:
        return False


def available_backends(lang="en"):
    found = []
    if _piper_bin() and piper_model(lang):
        found.append("piper")
    if _edge_ok():
        found.append("edge-tts")
    if _pyttsx3_engine():
        found.append("pyttsx3")
    found += [b for b in _BINARIES if shutil.which(b)]
    if sys.platform == "win32":
        found.append("powershell")
    if CONFIG["backend"] in found:
        found.remove(CONFIG["backend"]); found.insert(0, CONFIG["backend"])
    return found or ["noop"]


TTS_BACKEND = available_backends()[0]


def _binary_cmd(b, text, lang, wav=None):
    wpm = str(int(CONFIG["rate"]))
    if b == "powershell":
        out = ("$s.SetOutputToWaveFile('%s');" % wav) if wav else ""
        return ["powershell", "-Command", "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.Volume=%d;" % int(CONFIG["volume"] * 100) + out + "$s.Speak($args[0])", text]
    if b.startswith("espeak"):
        return [b, "-v", _espeak_voice(lang), "-s", wpm, "-p", "45", "-a", str(int(CONFIG["volume"] * 200))] \
            + (["-w", wav] if wav else []) + [text]
    if b == "say":
        return ["say", "-r", wpm] + (["-o", wav, "--data-format=LEI16@22050"] if wav else []) + [text]
    return None if wav else [b, "-l", _code(lang), text]


def _render(b, text, path, lang):
    if b == "piper":
        subprocess.run([_piper_bin(), "--model", piper_model(lang), "--output_file", path],
                       input=text.encode("utf-8"), timeout=120, capture_output=True)
    elif b == "edge-tts":
        mp3 = tempfile.mktemp(suffix=".mp3")
        try:
            pct = "%+d%%" % int((CONFIG["rate"] / 165.0 - 1) * 100)
            subprocess.run([sys.executable, "-m", "edge_tts", "--voice", EDGE_VOICES.get(_code(lang), EDGE_VOICES["en"]),
                            "--rate", pct, "--text", text, "--write-media", mp3], timeout=60, capture_output=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", mp3, path], timeout=60, capture_output=True)
        finally:
            if os.path.exists(mp3):
                os.remove(mp3)
    elif b == "pyttsx3":
        eng = _configured_engine(lang); eng.save_to_file(text, path); eng.runAndWait()
    else:
        cmd = _binary_cmd(b, text, lang, wav=path)
        if not cmd:
            return False
        subprocess.run(cmd, timeout=60, capture_output=True)
    return os.path.isfile(path) and os.path.getsize(path) > 44


def save_to_file(text: str, path: str, lang: str = "en"):
    """Render speech to a WAV file without audio hardware. Returns the backend used, or None."""
    for b in available_backends(lang):
        try:
            if b != "noop" and _render(b, text, path, lang):
                return b
        except Exception:
            continue
    return None


def _player():
    if sys.platform == "win32":
        return "winsound"
    for p in ("paplay", "aplay", "afplay", "ffplay"):
        if shutil.which(p):
            return p
    return None


def play_wav(path):
    p = _player()
    try:
        if p == "winsound":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME)
        elif p:
            cmd = [p, "-nodisp", "-autoexit", "-loglevel", "quiet", path] if p == "ffplay" else [p, path]
            return subprocess.run(cmd, timeout=120, capture_output=True).returncode == 0
        return p is not None
    except Exception:
        return False


def speak(text: str, lang: str = "en", dry_run: bool = False):
    """Speak text with the most natural voice available. Returns the backend used, or 'noop'. Never raises."""
    backends = available_backends(lang)
    if dry_run:
        return backends[0]
    wav = tempfile.mktemp(suffix=".wav")
    try:
        if _player():
            used = save_to_file(text, wav, lang)
            if used and play_wav(wav):
                return used
        for b in backends:  # no player: let the engine talk directly
            try:
                if b == "pyttsx3":
                    eng = _configured_engine(lang); eng.say(text); eng.runAndWait(); return b
                cmd = _binary_cmd(b, text, lang) if b not in ("piper", "edge-tts", "noop") else None
                if cmd and subprocess.run(cmd, timeout=60, capture_output=True).returncode == 0:
                    return b
            except Exception:
                continue
        return "noop"
    finally:
        if os.path.exists(wav):
            os.remove(wav)
