"""curses front-end for single-key navigation (colored tiles kept via 256-color pairs)."""
from .keys import (KeyState, handle_key, follow_focus, ansi_segments,
                   UP, DOWN, PGUP, PGDN, HOME, END, ENTER, BACKSPACE, ESC)
from .render import render_page

HELP = " n/p link  Enter open  1-9+Enter #  b/f back/fwd  g url  arrows/PgUp/PgDn scroll  q quit "


def available():
    try:
        import curses  # noqa: F401
        return True
    except ImportError:
        return False


def _keymap(curses):
    return {curses.KEY_UP: UP, curses.KEY_DOWN: DOWN, curses.KEY_PPAGE: PGUP, curses.KEY_NPAGE: PGDN,
            curses.KEY_HOME: HOME, curses.KEY_END: END, curses.KEY_ENTER: ENTER, 10: ENTER, 13: ENTER,
            curses.KEY_BACKSPACE: BACKSPACE, 127: BACKSPACE, 8: BACKSPACE, 27: ESC}


def run_curses(browser):
    import curses

    def main(scr):
        curses.curs_set(0); scr.keypad(True)
        pairs = {}
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors(); bg = -1
            except curses.error:
                bg = curses.COLOR_BLACK
        km = _keymap(curses)
        st = KeyState()

        def attr(color, bold):
            a = curses.A_BOLD if bold else 0
            if color is not None and curses.has_colors():
                c = color if color < curses.COLORS else color % 8
                if c not in pairs and len(pairs) + 1 < curses.COLOR_PAIRS:
                    pairs[c] = len(pairs) + 1
                    curses.init_pair(pairs[c], c, bg)
                if c in pairs:
                    a |= curses.color_pair(pairs[c])
            return a

        def prompt(label):
            h, w = scr.getmaxyx()
            curses.echo(); curses.curs_set(1)
            scr.move(h - 1, 0); scr.clrtoeol(); scr.addstr(h - 1, 0, label[:w - 1])
            try:
                s = scr.getstr(h - 1, len(label), max(1, w - len(label) - 1)).decode("utf-8", "replace")
            finally:
                curses.noecho(); curses.curs_set(0)
            return s

        lines, follow = [], True
        while True:
            h, w = scr.getmaxyx()
            st.page_h = max(1, h - 2)
            lines = render_page(browser.page, max(20, w - 1), True, browser.focus).split("\n")
            if follow:
                follow_focus(st, lines)
            st.scroll = min(st.scroll, max(0, len(lines) - st.page_h))
            scr.erase()
            bar = f" {browser.url}  [{st.scroll + 1}-{min(len(lines), st.scroll + st.page_h)}/{len(lines)}]"
            scr.addnstr(0, 0, bar.ljust(w - 1), w - 1, curses.A_REVERSE)
            for y, line in enumerate(lines[st.scroll:st.scroll + st.page_h], start=1):
                x = 0
                for text, color, bold in ansi_segments(line):
                    if x >= w - 1:
                        break
                    try:
                        scr.addnstr(y, x, text, w - 1 - x, attr(color, bold))
                    except curses.error:
                        pass
                    x += len(text)
            foot = st.status or (browser.error and "error: " + browser.error) or HELP
            scr.addnstr(h - 1, 0, foot.ljust(w - 1), w - 1, curses.A_REVERSE)
            scr.refresh()
            try:
                ch = scr.get_wch()
            except KeyboardInterrupt:
                return
            except curses.error:
                continue
            key = km.get(ch, ch if isinstance(ch, str) else "")
            if key == "\n":
                key = ENTER
            if key == curses.KEY_RESIZE:
                continue
            r = handle_key(browser, st, key, len(lines), prompt)
            if r == "quit":
                return
            follow = st.status == "follow" or key in (ENTER, "b", "f", "g")
            if st.status == "follow":
                st.status = ""

    curses.wrapper(main)
    return browser
