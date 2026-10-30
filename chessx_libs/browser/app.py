"""Interactive browser: history, link focus, keyboard commands."""
import shutil, sys
from .fetch import fetch, FetchError, DEMO_URL
from .parser import parse_html, Page, Block
from .render import render_page


class Browser:
    """State machine, no I/O except through `fetcher` -> testable headless."""

    def __init__(self, fetcher=fetch):
        self.fetcher, self.back_stack, self.fwd_stack = fetcher, [], []
        self.url, self.page, self.focus, self.error = None, Page(), 0, ""

    def _load(self, url):
        try:
            final, html = self.fetcher(url)
            self.page, self.url, self.error = parse_html(html, final), final, ""
        except FetchError as e:
            self.page, self.url, self.error = Page("Error", [Block("heading", "Page failed to load", 1), Block("text", str(e)),
                                                              Block("link", "Open demo page", href=DEMO_URL)]), url, str(e)
        self.focus = 0

    def open(self, url):
        if self.url is not None:
            self.back_stack.append(self.url)
        self.fwd_stack.clear(); self._load(url)

    def back(self):
        if self.back_stack:
            self.fwd_stack.append(self.url); self._load(self.back_stack.pop())

    def forward(self):
        if self.fwd_stack:
            self.back_stack.append(self.url); self._load(self.fwd_stack.pop())

    def next_link(self, d=1):
        if self.page.links:
            self.focus = (self.focus + d) % len(self.page.links)

    def follow(self, idx=None):
        links = self.page.links
        i = self.focus if idx is None else idx
        if 0 <= i < len(links):
            self.open(links[i].href)

    def handle(self, cmd: str) -> bool:
        """Apply a command; return False to quit."""
        c = cmd.strip()
        if c in ("q", "quit", "exit"):
            return False
        if c in ("n", "j"): self.next_link(1)
        elif c in ("p", "k"): self.next_link(-1)
        elif c in ("", "o"): self.follow()
        elif c == "b": self.back()
        elif c == "f": self.forward()
        elif c.isdigit(): self.follow(int(c) - 1)
        elif c.startswith("g "): self.open(c[2:].strip())
        elif "." in c or c.startswith("about:"): self.open(c)
        return True

    def screen(self, width=80, color=False):
        bar = f"[{self.url}]  back:{len(self.back_stack)} fwd:{len(self.fwd_stack)}"
        keys = "n/p link  Enter/# open  b/f back/fwd  g <url> go  q quit"
        return "\n".join([bar, render_page(self.page, width, color, self.focus), "", keys])


def run(url=None, input_fn=input, out=None):
    """Interactive loop for chessx.py's menu. Uses Rich for output if available."""
    out = out or sys.stdout
    try:
        from rich.console import Console
        from rich.text import Text
        con = Console(file=out)
        show = lambda s: con.print(Text.from_ansi(s))
    except ImportError:
        show = lambda s: print(s, file=out)
    b = Browser(); b.open(url or DEMO_URL)
    while True:
        w = shutil.get_terminal_size((80, 24)).columns
        if out.isatty():
            out.write("\033[2J\033[H")
        show(b.screen(w - 1, color=True))
        try:
            cmd = input_fn("> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not b.handle(cmd):
            break
    return b
