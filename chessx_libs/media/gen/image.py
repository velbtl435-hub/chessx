"""Chessboard / position images from FEN and simple banners (Pillow optional)."""
import os
from ._deps import need_pil
from .board import parse_fen

GLYPHS = dict(zip("KQRBNPkqrbnp", "♔♕♖♗♘♙♚♛♜♝♞♟"))
FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
              "/Library/Fonts/Arial Unicode.ttf", "C:/Windows/Fonts/seguisym.ttf"]


def _font(size):
    _, _, ImageFont = need_pil()
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size), True
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size), False
    except TypeError:
        return ImageFont.load_default(), False


def board_image(fen, square=60, light=(240, 217, 181), dark=(181, 136, 99), flip=False,
                coords=True, highlight=()):
    """Return a PIL.Image of the position. highlight: squares like ['e2','e4']."""
    Image, ImageDraw, _ = need_pil()
    board, _side = parse_fen(fen)
    m = square // 3 if coords else 0
    img = Image.new("RGB", (8 * square + m, 8 * square + m), (60, 60, 60))
    d = ImageDraw.Draw(img)
    font, unicode_ok = _font(int(square * 0.8))
    small, _ = _font(max(10, square // 5))
    hl = set(highlight)
    for r in range(8):
        for c in range(8):
            br, bc = (7 - r, 7 - c) if flip else (r, c)
            name = "abcdefgh"[bc] + str(8 - br)
            x, y = m + c * square, r * square
            col = (246, 246, 105) if name in hl else (light if (r + c) % 2 == 0 else dark)
            d.rectangle([x, y, x + square - 1, y + square - 1], fill=col)
            p = board[br][bc]
            if p:
                if unicode_ok:
                    d.text((x + square / 2, y + square / 2), GLYPHS[p], fill=(0, 0, 0), font=font, anchor="mm")
                else:  # fallback: disc with letter
                    fill, ink = ((255, 255, 255), (0, 0, 0)) if p.isupper() else ((20, 20, 20), (255, 255, 255))
                    pad = square // 8
                    d.ellipse([x + pad, y + pad, x + square - pad, y + square - pad], fill=fill, outline=(0, 0, 0))
                    d.text((x + square / 2, y + square / 2), p.upper(), fill=ink, font=small, anchor="mm")
        if coords:
            d.text((m / 2, r * square + square / 2), str(8 - (7 - r if flip else r)), fill=(220, 220, 220), font=small, anchor="mm")
    if coords:
        for c in range(8):
            d.text((m + c * square + square / 2, 8 * square + m / 2), "abcdefgh"[7 - c if flip else c],
                   fill=(220, 220, 220), font=small, anchor="mm")
    return img


def save_board(fen, path, **kw):
    board_image(fen, **kw).save(path)
    return str(path)


def banner(text, size=(800, 200), bg=(30, 30, 40), fg=(240, 240, 240), accent=(181, 136, 99), path=None):
    """Simple banner with a checkered strip; returns Image (and saves if path)."""
    Image, ImageDraw, _ = need_pil()
    w, h = size
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    s = max(8, h // 10)
    for i in range(0, w, s):
        for j, yy in enumerate((0, h - s)):
            if ((i // s) + j) % 2 == 0:
                d.rectangle([i, yy, i + s - 1, yy + s - 1], fill=accent)
    fs = max(10, h // 3)
    font, _ = _font(fs)
    while fs > 10 and d.textlength(text, font=font) > w * 0.9:
        fs -= 2
        font, _ = _font(fs)
    d.text((w / 2, h / 2), text, fill=fg, font=font, anchor="mm")
    if path:
        img.save(path)
    return img
