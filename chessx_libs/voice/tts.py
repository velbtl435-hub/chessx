"""Text-to-speech. Order: pyttsx3 (optional) -> OS binary (espeak-ng/espeak/say/spd-say/PowerShell) -> noop."""
import shutil, subprocess, sys

try:
    import pyttsx3  # optional
except Exception:
    pyttsx3 = None

LANG_VOICE = {"en": "en", "pt": "pt-br", "ja": "ja"}


def available_backends():
    found = ["pyttsx3"] if pyttsx3 else []
    found += [b for b in ("espeak-ng", "espeak", "say", "spd-say") if shutil.which(b)]
    if sys.platform == "win32":
        found.append("powershell")
    return found or ["noop"]


TTS_BACKEND = available_backends()[0]


def speak(text: str, lang: str = "en", dry_run: bool = False):
    """Returns the backend/command used; never raises. 'noop' = silent fallback."""
    b = available_backends()[0]
    if b == "noop":
        return "noop"
    if b == "pyttsx3":
        if not dry_run:
            try:
                eng = pyttsx3.init(); eng.say(text); eng.runAndWait()
            except Exception:
                return "noop"
        return "pyttsx3"
    if b == "powershell":
        cmd = ["powershell", "-Command",
               "Add-Type -AssemblyName System.Speech;(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($args[0])", text]
    elif b.startswith("espeak"):
        cmd = [b, "-v", LANG_VOICE.get(lang, "en"), text]
    else:
        cmd = [b, text]
    if not dry_run:
        try:
            subprocess.run(cmd, check=False, timeout=60, capture_output=True)
        except Exception:
            return "noop"
    return cmd
