"""Speech-to-text. Order: vosk (offline, optional) -> SpeechRecognition (optional) -> noop (returns None)."""
import json, wave

try:
    import vosk  # optional
except Exception:
    vosk = None
try:
    import speech_recognition as sr  # optional
except Exception:
    sr = None

STT_BACKEND = "vosk" if vosk else ("speech_recognition" if sr else "noop")


def transcribe_file(path: str, model_path: str = None, lang: str = "en-US"):
    """Transcribe a WAV file. Returns text, or None when no backend is available."""
    if vosk and model_path:
        wf = wave.open(path, "rb")
        rec = vosk.KaldiRecognizer(vosk.Model(model_path), wf.getframerate())
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)
        return json.loads(rec.FinalResult()).get("text", "")
    if sr:
        r = sr.Recognizer()
        with sr.AudioFile(path) as src:
            audio = r.record(src)
        try:
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
