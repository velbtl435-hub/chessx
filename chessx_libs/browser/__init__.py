"""ChessX ASCII browser (PRIORITY #4): pages rendered as colored square tiles.

API:  run(url=None)  -> interactive browser (Rich if present, plain fallback)
      render_page(html, width=80, color=False, focus=None) -> str
      parse_html(html, base_url="") -> Page
"""
from .parser import Block, Page, parse_html
from .render import render_page, TILE_COLORS
from .fetch import fetch, FetchError, DEMO_URL, DEMO_HTML
from .app import Browser, run

__all__ = ["run", "render_page", "parse_html", "fetch", "FetchError", "Browser",
           "Block", "Page", "TILE_COLORS", "DEMO_URL", "DEMO_HTML"]
