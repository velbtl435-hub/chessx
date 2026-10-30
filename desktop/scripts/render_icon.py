#!/usr/bin/env python3
"""Render assets/knight.txt (ASCII chess knight) into a 1024x1024 PNG app icon.
Then run `npx tauri icon assets/chessx-knight-1024.png` to regenerate src-tauri/icons/*."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
SIZE, PAD = 1024, 120
BG, FG, GLOW = (11, 15, 12, 255), (57, 255, 106, 255), (57, 255, 106, 110)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consolab.ttf",
]


def font(size):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def main():
    lines = open(os.path.join(ASSETS, "knight.txt"), encoding="utf-8").read().rstrip("\n").split("\n")
    cols, rows = max(map(len, lines)), len(lines)
    # largest font that fits the box
    size = 10
    while True:
        f = font(size + 1)
        w = f.getbbox("M" * cols)[2]
        h = (size + 1) * 1.15 * rows
        if w > SIZE - 2 * PAD or h > SIZE - 2 * PAD:
            break
        size += 1
    f = font(size)
    lh = size * 1.15
    tw, th = f.getbbox("M" * cols)[2], lh * rows
    x0, y0 = (SIZE - tw) / 2, (SIZE - th) / 2

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=180, fill=BG, outline=FG, width=14)
    text = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    td = ImageDraw.Draw(text)
    for i, line in enumerate(lines):
        td.text((x0, y0 + i * lh), line, font=f, fill=FG)
    glow = text.copy()
    glow.putalpha(text.getchannel("A").point(lambda a: GLOW[3] if a else 0))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(text)
    out = os.path.join(ASSETS, "chessx-knight-1024.png")
    img.save(out)
    print("icon ->", out)


if __name__ == "__main__":
    main()
