import sys
from . import run
args = [a for a in sys.argv[1:] if not a.startswith("--")]
mode = "prompt" if "--prompt" in sys.argv else "keys" if "--keys" in sys.argv else None
run(args[0] if args else None, mode=mode)
