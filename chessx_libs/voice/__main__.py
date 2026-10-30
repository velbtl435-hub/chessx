"""CLI: python -m chessx_libs.voice "texto" [--lang pt] [--robot] [-o out.wav] | --voices | --transcribe f.wav"""
import argparse, json
from . import tts, stt, lang as L


def main(argv=None):
    ap = argparse.ArgumentParser(prog="chessx-voice")
    ap.add_argument("text", nargs="?")
    ap.add_argument("--lang", default=None, help="en | pt | ja")
    ap.add_argument("--robot", action="store_true", help="robot voice")
    ap.add_argument("-o", "--out", help="write WAV instead of playing")
    ap.add_argument("--rate", type=int); ap.add_argument("--volume", type=float)
    ap.add_argument("--voices", action="store_true", help="list pyttsx3 voices for --lang")
    ap.add_argument("--transcribe", metavar="WAV")
    a = ap.parse_args(argv)
    if a.rate: tts.configure(rate=a.rate)
    if a.volume is not None: tts.configure(volume=a.volume)
    lg = L.current_lang(a.lang)
    if a.voices:
        print(json.dumps(tts.list_voices(lg), ensure_ascii=False, indent=1)); return 0
    if a.transcribe:
        print(stt.transcribe_file(a.transcribe, lang=lg)); return 0
    if not a.text:
        ap.print_help(); return 1
    if a.out:
        print(tts.save_to_file(a.text, a.out, lg, robot=a.robot)); return 0
    print(tts.speak(a.text, lg, robot=a.robot)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
