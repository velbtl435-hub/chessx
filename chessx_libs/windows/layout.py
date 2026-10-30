import shutil, unicodedata
from dataclasses import dataclass, field
from typing import List


def _w(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _fit(s: str, width: int) -> str:
    out, w = "", 0
    for c in s:
        cw = _w(c)
        if w + cw > width:
            break
        out += c; w += cw
    return out + " " * (width - w)


@dataclass
class Pane:
    title: str
    lines: List[str] = field(default_factory=list)
    scroll: int = 0

    def write(self, text: str):
        self.lines.extend(str(text).splitlines() or [""])

    def view(self, height: int) -> List[str]:
        start = max(0, len(self.lines) - height - self.scroll)
        return self.lines[start:start + height]


class TabBar:
    def __init__(self):
        self.tabs: List[Pane] = []
        self.active = 0

    def open(self, title: str, content: str = "") -> Pane:
        for i, t in enumerate(self.tabs):
            if t.title == title:
                self.active = i
                return t
        p = Pane(title); p.write(content); self.tabs.append(p)
        self.active = len(self.tabs) - 1
        return p

    def close(self, idx: int = None):
        if self.tabs:
            self.tabs.pop(self.active if idx is None else idx)
            self.active = max(0, min(self.active, len(self.tabs) - 1))

    def cycle(self, step: int = 1):
        if self.tabs:
            self.active = (self.active + step) % len(self.tabs)

    def current(self):
        return self.tabs[self.active] if self.tabs else Pane("untitled")

    def render(self, width: int) -> str:
        s = "".join((f"[{t.title}]" if i == self.active else f" {t.title} ") + "│" for i, t in enumerate(self.tabs))
        return _fit(s, width)


class Layout:
    def __init__(self, width: int = None, height: int = None, side_w: int = 20, term_h: int = 6, mirror: bool = True):
        size = shutil.get_terminal_size((100, 30))
        self.width, self.height = width or size.columns, height or size.lines
        self.side_w, self.term_h, self.mirror = side_w, term_h, mirror
        self.left, self.right = Pane("EXPLORER"), Pane("OUTLINE")
        self.editor, self.terminal = TabBar(), Pane("TERMINAL")
        self.show_left = self.show_right = True

    def toggle(self, which: str):
        setattr(self, f"show_{which}", not getattr(self, f"show_{which}"))

    def render(self) -> str:
        W, H = self.width, self.height
        lw = self.side_w if self.show_left else 0
        rw = self.side_w if self.show_right else 0
        ew = W - lw - rw - (1 if lw else 0) - (1 if rw else 0)
        body_h = H - self.term_h - 3
        cur = self.editor.current()
        out = ["┌" + "─" * (W - 2) + "┐"]
        hdr = (_fit(self.left.title, lw) + "│" if lw else "") + self.editor.render(ew) + ("│" + _fit(self.right.title, rw) if rw else "")
        out.append(_fit(hdr, W))
        lv, ev, rv = self.left.view(body_h), cur.view(body_h), self.right.view(body_h)
        for i in range(body_h):
            row = ""
            if lw:
                row += _fit(lv[i] if i < len(lv) else "", lw) + "│"
            row += _fit(ev[i] if i < len(ev) else "", ew)
            if rw:
                txt = rv[i] if i < len(rv) else ""
                row += "│" + (_fit(txt.strip().rjust(rw), rw) if self.mirror else _fit(txt, rw))
            out.append(_fit(row, W))
        out.append(_fit("─" * 2 + " " + self.terminal.title + " " + "─" * W, W))
        for ln in self.terminal.view(self.term_h):
            out.append(_fit("$ " + ln, W))
        out += [" " * W] * (H - len(out))
        return "\n".join(out[:H])
