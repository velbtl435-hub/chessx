"""Text-to-speech. Order: pyttsx3 (optional) -> OS binary (espeak-ng/espeak/say/spd-say/PowerShell) -> noop.

Never raises: if a backend fails (e.g. pyttsx3 installed but no eSpeak library), the next one is tried.
"""
import os, shutil, subprocess, sys

try:
    import pyttsx3  # optional
except Exception:
    pyttsx3 = None

LANG_VOICE = {"en": "en-us", "pt": "pt-br", "ja": "ja"}
_BINARIES = ("espeak-ng", "espeak", "say", "spd-say")


def _pyttsx3_engine():
    if not pyttsx3:
        return None
    try:
        return pyttsx3.init()
    except Exception:  # e.g. RuntimeError: eSpeak not installed
        return None


def available_backends():
    found = ["pyttsx3"] if _pyttsx3_engine() else []
    found += [b for b in _BINARIES if shutil.which(b)]
    if sys.platform == "win32":
        found.append("powershell")
    return found or ["noop"]


TTS_BACKEND = available_backends()[0]


def _binary_cmd(b, text, lang, wav=None):
    if b == "powershell":
        out = ("$s.SetOutputToWaveFile('%s');" % wav) if wav else ""
        return ["powershell", "-Command", "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;" + out + "$s.Speak($args[0])", text]
    if b.startswith("espeak"):
        return [b, "-v", LANG_VOICE.get(lang, "en-us")] + (["-w", wav] if wav else []) + [text]
    if b == "say":
        return ["say"] + (["-o", wav, "--data-format=LEI16@22050"] if wav else []) + [text]
    return None if wav else [b, text]


def speak(text: str, lang: str = "en", dry_run: bool = False):
    """Speak text. Returns the backend name/command used, or 'noop'. Never raises."""
    for b in available_backends():
        if b == "noop":
            return "noop"
        if b == "pyttsx3":
            if dry_run:
                return "pyttsx3"
            try:
                eng = _pyttsx3_engine(); eng.say(text); eng.runAndWait()
                return "pyttsx3"
            except Exception:
                continue
        cmd = _binary_cmd(b, text, lang)
        if not cmd:
            continue
        if dry_run:
            return cmd
        try:
            if subprocess.run(cmd, timeout=60, capture_output=True).returncode == 0:
                return cmd
        except Exception:
            continue
    return "noop"


def save_to_file(text: str, path: str, lang: str = "en"):
    """Render speech to a WAV file without audio hardware. Returns the backend used, or None."""
    for b in available_backends():
        try:
            if b == "pyttsx3":
                eng = _pyttsx3_engine(); eng.save_to_file(text, path); eng.runAndWait()
            else:
                cmd = _binary_cmd(b, text, lang, wav=path)
                if not cmd:
                    continue
                subprocess.run(cmd, timeout=60, capture_output=True)
            if os.path.isfile(path) and os.path.getsize(path) > 44:
                return b
        except Exception:
            continue
    return None
