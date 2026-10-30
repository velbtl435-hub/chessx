"""HTML -> list of blocks (stdlib html.parser only)."""
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

SKIP = {"script", "style", "noscript", "head", "svg", "template"}
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 4, "h6": 4}
BLOCKY = {"p", "div", "section", "article", "br", "tr", "pre", "blockquote", "header", "footer", "nav", "main", "table", "ul", "ol"}


@dataclass
class Block:
    kind: str            # heading | text | link | item | image
    text: str
    level: int = 0
    href: str = ""


@dataclass
class Page:
    title: str = ""
    blocks: list = field(default_factory=list)

    @property
    def links(self):
        return [b for b in self.blocks if b.kind == "link"]


class _P(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.page, self.buf = base, Page(), []
        self.skip = 0; self.kind = "text"; self.level = 0
        self.href = None; self.link_buf = []; self.in_title = False

    def _flush(self):
        t = " ".join("".join(self.buf).split())
        self.buf = []
        if t:
            self.page.blocks.append(Block(self.kind, t, self.level))
        self.kind, self.level = "text", 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            if tag == "head":
                return
            self.skip += 1; return
        if tag == "title":
            self.in_title = True; return
        if tag in HEADINGS:
            self._flush(); self.kind, self.level = "heading", HEADINGS[tag]
        elif tag == "li":
            self._flush(); self.kind = "item"
        elif tag in BLOCKY:
            self._flush()
        elif tag == "img":
            self._flush()
            self.page.blocks.append(Block("image", a.get("alt") or a.get("src", "image").rsplit("/", 1)[-1] or "image"))
        elif tag == "a" and a.get("href") and not a["href"].startswith(("javascript:", "#")):
            self._flush(); self.href = urljoin(self.base, a["href"]); self.link_buf = []

    def handle_endtag(self, tag):
        if tag in SKIP and tag != "head":
            self.skip = max(0, self.skip - 1); return
        if tag == "title":
            self.in_title = False; return
        if tag == "a" and self.href is not None:
            t = " ".join("".join(self.link_buf).split()) or self.href
            self.page.blocks.append(Block("link", t, href=self.href)); self.href = None
        elif tag in HEADINGS or tag == "li" or tag in BLOCKY:
            self._flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_title:
            self.page.title += data.strip(); return
        (self.link_buf if self.href is not None else self.buf).append(data)

    def close(self):
        super().close(); self._flush()


def parse_html(html: str, base_url: str = "") -> Page:
    p = _P(base_url); p.feed(html or ""); p.close()
    return p.page
