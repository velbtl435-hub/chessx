"""Single-keystroke navigation. `handle_key` is pure (no terminal) and drives a Browser."""
import re
from dataclasses import dataclass

# normalized key names produced by the curses/termios readers
UP, DOWN, PGUP, PGDN, HOME, END, ENTER, BACKSPACE, ESC = "UP", "DOWN", "PGUP", "PGDN", "HOME", "END", "ENTER", "BACKSPACE", "ESC"


@dataclass
class KeyState:
    scroll: int = 0
    digits: str = ""
    page_h: int = 20
    status: str = ""


def _focus_line(browser, lines):
    """Line index of the focused link in the rendered page (▶ marker)."""
    for i, l in enumerate(lines):
        if "\u25b6 [" in l:
            return i
    return None


def handle_key(browser, st: KeyState, key: str, total_lines: int = 0, prompt=None) -> str:
    """Apply one key. Returns 'quit', 'redraw' or 'noop'. `prompt(label)->str|None` is used by 'g'."""
    max_scroll = max(0, total_lines - st.page_h)
    st.status = ""
    if st.digits and key not in (ENTER, BACKSPACE, ESC) and not key.isdigit():
        st.digits = ""
    if key in ("q", "Q"):
        return "quit"
    if len(key) == 1 and key.isdigit():
        st.digits += key; st.status = f"open link #{st.digits} (Enter)"; return "redraw"
    if key == BACKSPACE and st.digits:
        st.digits = st.digits[:-1]; return "redraw"
    if key == ESC:
        st.digits = ""; return "redraw"
    if key == ENTER:
        before = browser.url
        if st.digits:
            n = int(st.digits); st.digits = ""
            if not 1 <= n <= len(browser.page.links):
                st.status = f"no link #{n}"; return "redraw"
            browser.follow(n - 1)
        else:
            browser.follow()
        if browser.url != before or browser.error:
            st.scroll = 0
        return "redraw"
    if key in ("n", "\t", "j"):
        browser.next_link(1); st.status = "follow"; return "redraw"
    if key in ("p", "k"):
        browser.next_link(-1); st.status = "follow"; return "redraw"
    if key == "b":
        browser.back(); st.scroll = 0; return "redraw"
    if key == "f":
        browser.forward(); st.scroll = 0; return "redraw"
    if key == "g":
        url = prompt("url: ") if prompt else None
        if url and url.strip():
            browser.open(url.strip()); st.scroll = 0
        return "redraw"
    if key == DOWN:
        st.scroll = min(max_scroll, st.scroll + 1)
    elif key == UP:
        st.scroll = max(0, st.scroll - 1)
    elif key in (PGDN, " "):
        st.scroll = min(max_scroll, st.scroll + st.page_h - 1)
    elif key == PGUP:
        st.scroll = max(0, st.scroll - st.page_h + 1)
    elif key == HOME:
        st.scroll = 0
    elif key == END:
        st.scroll = max_scroll
    else:
        return "noop"
    return "redraw"


def follow_focus(st: KeyState, lines):
    """Scroll so the focused link is visible."""
    i = _focus_line(None, lines)
    if i is None:
        return
    if i < st.scroll:
        st.scroll = i
    elif i >= st.scroll + st.page_h:
        st.scroll = i - st.page_h + 1


_ANSI = re.compile(r"\033\[([0-9;]*)m")


def ansi_segments(line):
    """Split an ANSI line into (text, color256|None, bold) segments for curses."""
    out, pos, color, bold = [], 0, None, False
    for m in _ANSI.finditer(line):
        if m.start() > pos:
            out.append((line[pos:m.start()], color, bold))
        codes = [c for c in m.group(1).split(";") if c]
        if not codes or codes == ["0"]:
            color, bold = None, False
        else:
            if "1" in codes:
                bold = True
            if "38" in codes and len(codes) > codes.index("38") + 2:
                color = int(codes[codes.index("38") + 2])
        pos = m.end()
    if pos < len(line):
        out.append((line[pos:], color, bold))
    return out
