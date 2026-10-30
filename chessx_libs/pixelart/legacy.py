"""Legacy 3x5 font + simple char-grid sprites (formerly chessx_libs.interface.pixelart).

Behavior is identical to the old module; chessx_libs.interface.pixelart now re-exports these.
"""
import os, sys


class Color:  # same codes as chessx_libs.interface.colors.Color (kept local to avoid a cycle)
    TEAL = "\033[38;5;37m"
    RESET = "\033[0m"


def paint(text: str, color: str, force: bool = False) -> str:
    on = force or (sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
    return f"{color}{text}{Color.RESET}" if on else text


PIXEL_FROM = ".#oO+"
PIXEL_TO = " █▓▒░"
if len(PIXEL_FROM) != len(PIXEL_TO):  # guard (assert can be stripped with -O)
    raise ValueError("pixel maketrans tables must have equal length")
PIXEL_TABLE = str.maketrans(PIXEL_FROM, PIXEL_TO)

SPRITES = {
    "knight": ["..###.", ".#####", "##o##.", ".####.", "..###.", ".#####"],
    "slime": ["..oo..", ".oOOo.", "oO##Oo", "oOOOOo", ".oooo."],
    "ghost": [".####.", "#o##o#", "######", "######", "#.##.#"],
}

FONT = {
    "A": ["###", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": ["###", "#..", "#..", "#..", "###"], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"], "F": ["###", "#..", "##.", "#..", "#.."],
    "G": ["###", "#..", "#.#", "#.#", "###"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"], "J": ["..#", "..#", "..#", "#.#", "###"],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": ["###", "#.#", "#.#", "#.#", "###"], "P": ["###", "#.#", "###", "#..", "#.."],
    "Q": ["###", "#.#", "#.#", "###", "..#"], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": ["###", "#..", "###", "..#", "###"], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"], "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"], "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."], "Z": ["###", "..#", ".#.", "#..", "###"],
    " ": ["...", "...", "...", "...", "..."],
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
}


def render_sprite(name_or_rows, color: str = Color.TEAL, force_color: bool = False) -> str:
    rows = SPRITES[name_or_rows] if isinstance(name_or_rows, str) else name_or_rows
    return "\n".join(paint(r.translate(PIXEL_TABLE), color, force_color) for r in rows)


def retro_text(text: str) -> str:
    glyphs = [FONT.get(ch, FONT[" "]) for ch in text.upper()]
    return "\n".join(" ".join(g[r] for g in glyphs).translate(PIXEL_TABLE) for r in range(5))
