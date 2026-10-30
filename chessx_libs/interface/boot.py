"""Linux-style boot sequence with ASCII knight (sideways, angled upward)."""
import sys, time
from .colors import Color, paint

KNIGHT = r"""
        __/\__
      _/  o   \
     /  __     >
    /  /  \___/
   |  |
   /   \___
  /________\
 [__________]
"""

MODULES = ["kernel", "i18n", "search.engines", "search.fusion", "interface.board",
           "crypto", "media", "reversing", "chess_ai", "voice"]


def boot_sequence(duration: float = 6.0, out=sys.stdout, enabled: bool = True):
    if not enabled:
        return
    step = duration / (len(MODULES) + 2)
    print(paint(KNIGHT, Color.PURPLE), file=out)
    for i, mod in enumerate(MODULES):
        col = (Color.TEAL, Color.BLUE, Color.ORANGE)[i % 3]
        print(f"[{paint(' OK ', Color.TEAL)}] {paint('loading', Color.GRAY)} {paint(mod, col)}", file=out)
        out.flush()
        time.sleep(step)
    time.sleep(step)
    print(paint("\n  C h e s s X\n", Color.BOLD + Color.ORANGE), file=out)
