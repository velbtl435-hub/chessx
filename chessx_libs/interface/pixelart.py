"""Pixel-art sprites and a 3x5 retro font.

Fix: the old str.maketrans() call used FROM/TO strings of different lengths,
raising ValueError. Both are now the same length and checked at import time.
"""
from .colors import Color, paint

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
