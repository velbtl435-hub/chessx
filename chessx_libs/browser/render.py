"""Render a Page as colored square tiles. Pure function: returns a string."""
import textwrap
from .parser import Page, parse_html

TILE = "\u25a0"  # ■
# kind -> (ANSI 256 color, tile glyph)
TILE_COLORS = {"heading": 214, "text": 250, "link": 45, "item": 120, "image": 171}


def _c(s, code, color, bold=False):
    if not color:
        return s
    return f"\033[{'1;' if bold else ''}38;5;{code}m{s}\033[0m"


def render_page(html_or_page, width: int = 80, color: bool = False, focus=None) -> str:
    """html (str) or Page -> text. Each block is prefixed by a colored tile; links are numbered;
    `focus` is the index of the selected link (highlighted with ▶)."""
    page = html_or_page if isinstance(html_or_page, Page) else parse_html(html_or_page)
    width = max(20, int(width))
    out = []
    if page.title:
        bar = TILE * width
        out += [_c(bar, 214, color), _c(page.title[:width].center(width), 214, color, True), _c(bar, 214, color)]
    li = 0
    for b in page.blocks:
        code = TILE_COLORS.get(b.kind, 250)
        if b.kind == "heading":
            tiles = TILE * max(1, 5 - b.level)
            body = textwrap.wrap(b.text.upper() if b.level == 1 else b.text, width - len(tiles) - 1) or [""]
            out.append("")
            out += [_c(f"{tiles} {l}", code, color, True) for l in body]
        elif b.kind == "image":
            w = min(width, max(12, len(b.text) + 6))
            out.append(_c("\u2592" * w, code, color))
            out.append(_c(f"\u2592 [img] {b.text}"[:w - 1].ljust(w - 1) + "\u2592", code, color))
            out.append(_c("\u2592" * w, code, color))
        elif b.kind == "link":
            mark = "\u25b6" if focus == li else TILE
            lab = f"{mark} [{li + 1}] {b.text}"
            out.append(_c(textwrap.shorten(lab, width, placeholder="…"), 51 if focus == li else code, color, focus == li))
            li += 1
        else:
            pre = TILE + " " if b.kind == "item" else "  "
            for i, l in enumerate(textwrap.wrap(b.text, width - 2) or [""]):
                out.append(_c((pre if i == 0 else "  ") + l, code, color))
    return "\n".join(out)
