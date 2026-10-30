"""Interpret equations drawn in the terminal as ASCII / Unicode art, and render back.

Supported drawings (combine freely, separate side-by-side pieces by at least one blank column):
  stacked fraction      x + 1          superscript (line above)    2
                        -----                                    x  + 3x
                          2
  square root            ____  /  ___      subscript (line below)   a  + a
                       \\/ x+1   √ 2x                                1    2
  matrix                [1  2]   (also ⎡ ⎤ ⎣ ⎦ | |)
                        [3  4]
  integral   2          or ASCII   /2         sum     n
             ∫ x^2 dx              | x dx             Σ  k^2
             0                     /0                k=1
"""
import re

import sympy as sp

from .core import parse

BAR = set("-─—―_")
LBR, RBR = set("[⎡⎢⎣|"), set("]⎤⎥⎦|")
_PH = 0xE000          # private-use placeholders for matrices


def grid(text_or_lines):
    lines = text_or_lines.splitlines() if isinstance(text_or_lines, str) else list(text_or_lines)
    lines = [l.replace("\t", "    ").rstrip() for l in lines]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    w = max((len(l) for l in lines), default=0)
    return [list(l.ljust(w)) for l in lines]


def _trim(g):
    g = [r for r in g]
    while g and not "".join(g[0]).strip():
        g.pop(0)
    while g and not "".join(g[-1]).strip():
        g.pop()
    if not g:
        return []
    cols = [c for c in range(len(g[0])) if any(r[c] != " " for r in g)]
    a, b = cols[0], cols[-1] + 1
    return [r[a:b] for r in g]


class Interpreter:
    def __init__(self):
        self.ph = {}

    def run(self, text):
        g = grid(text)
        if not g:
            raise ValueError("empty drawing")
        return self.block(g)

    # ------------------------------------------------------------------ blocks
    def block(self, g):
        g = _trim(g)
        if not g:
            return ""
        if len(g) == 1:
            return self.inline("".join(g[0]))
        g = [r[:] for r in g]
        self._matrices(g)
        g = _trim(g)
        if len(g) == 1:
            return self.inline("".join(g[0]))
        boxes = self._boxes(g)
        base = self._baseline(g, boxes)
        self._bigops(g, base)
        self._roots_mark(g, base)
        boxes = self._boxes(g)
        parts = []
        for a, b in boxes:
            sub = [r[a:b] for r in g]
            frac = self._fraction(sub)
            if frac:
                parts.append(frac)
            else:
                parts.append(self.simple(sub, base, a))
        return _join(parts)

    def _boxes(self, g):
        w = len(g[0]); out = []; start = None
        for c in range(w + 1):
            blank = c == w or all(r[c] == " " for r in g)
            if not blank and start is None:
                start = c
            if blank and start is not None:
                out.append((start, c)); start = None
        return out

    def _bar_row(self, sub):
        sub_t = sub
        w = len(sub_t[0])
        for i, r in enumerate(sub_t):
            s = "".join(r).strip()
            if (len(s) >= 2 and set(s) <= BAR and len(s) >= 0.75 * w and 0 < i < len(sub_t) - 1
                    and "".join(sum(sub_t[:i], [])).strip() and "".join(sum(sub_t[i + 1:], [])).strip()):
                return i
        return None

    def _baseline(self, g, boxes):
        for a, b in boxes:
            r = self._bar_row([row[a:b] for row in g])
            if r is not None and all(g[r][c] in BAR or g[r][c] == " " for c in range(a, b)):
                return r
        counts = [sum(ch not in " _‾" for ch in row) for row in g]
        return counts.index(max(counts))

    def _fraction(self, sub):
        sub = _trim(sub)
        if len(sub) < 3:
            return None
        r = self._bar_row(sub)
        if r is None:
            return None
        num, den = self.block(sub[:r]), self.block(sub[r + 1:])
        return "((%s)/(%s))" % (num, den)

    # ------------------------------------------------------------- matrices
    def _matrices(self, g):
        h, w = len(g), len(g[0])
        for c in range(w):
            r = 0
            while r < h:
                if g[r][c] in LBR and g[r][c] != "|" or (g[r][c] == "|" and r + 1 < h and g[r + 1][c] == "|"):
                    r2 = r
                    while r2 < h and g[r2][c] in LBR:
                        r2 += 1
                    if r2 - r >= 2:
                        for c2 in range(c + 1, w):
                            if all(g[k][c2] in RBR for k in range(r, r2)):
                                rows = []
                                for k in range(r, r2):
                                    cells = "".join(g[k][c + 1:c2]).strip()
                                    rows.append(cells)
                                sep = r"\s{2,}|\s*,\s*" if any(re.search(r"\s{2,}|,", x) for x in rows) else r"\s+"
                                ent = [[self.inline(e) for e in re.split(sep, x) if e] for x in rows]
                                key = chr(_PH + len(self.ph))
                                self.ph[key] = "Matrix([%s])" % ", ".join("[%s]" % ", ".join(e) for e in ent)
                                for k in range(r, r2):
                                    for cc in range(c, c2 + 1):
                                        g[k][cc] = " "
                                g[(r + r2 - 1) // 2][c] = key
                                break
                    r = r2 if r2 > r else r + 1
                else:
                    r += 1

    # --------------------------------------------------------- big operators
    def _run(self, row, c):
        """Text of the non-space run touching column c (or starting right after it) in row; blanks it."""
        if c >= len(row):
            return ""
        a = c
        if row[a] == " ":
            return ""
        while a > 0 and row[a - 1] != " ":
            a -= 1
        b = c
        while b < len(row) and row[b] != " ":
            b += 1
        s = "".join(row[a:b])
        for k in range(a, b):
            row[k] = " "
        return s

    def _bigops(self, g, b):
        h = len(g)
        for c in range(len(g[0])):
            ch = g[b][c]
            up = g[b - 1] if b > 0 else None
            dn = g[b + 1] if b + 1 < h else None
            if ch == "|" and up and dn and up[c] in "/⌠," and dn[c] in "/⌡`":
                up[c] = dn[c] = " "
                hi = self._run(up, c + 1) if c + 1 < len(up) and up[c + 1] != " " else ""
                lo = self._run(dn, c + 1) if c + 1 < len(dn) and dn[c + 1] != " " else ""
                up[c] = dn[c] = " "
                g[b][c] = "∫"
                self.ph.setdefault("lim", {})[(b, c)] = (lo, hi)
            elif ch in "∫∑Σ":
                hi = self._run(up, c) if up else ""
                lo = self._run(dn, c) if dn else ""
                self.ph.setdefault("lim", {})[(b, c)] = (lo, hi)

    def _roots_mark(self, g, b):
        """Turn '\\/' + overbar into '√' so the sqrt stays on the baseline."""
        row = g[b]
        for c in range(len(row) - 1):
            if row[c] == "\\" and row[c + 1] == "/":
                row[c] = " "; row[c + 1] = "√"

    # -------------------------------------------------------- simple boxes
    def simple(self, sub, b, off=0):
        h, w = len(sub), len(sub[0])
        out = []
        c = 0
        while c < w:
            ch = sub[b][c]
            if ch == "√":
                end = c + 1
                bar_row = b - 1 if b > 0 else None
                if bar_row is not None and c + 1 < w and sub[bar_row][c + 1] in "_‾":
                    while end < w and sub[bar_row][end] in "_‾":
                        end += 1
                    rad = [r[c + 1:end] for r in sub]
                    rad[bar_row] = [" " if x in "_‾" else x for x in rad[bar_row]]
                    out.append("sqrt(%s)" % self.block(rad))
                    c = end
                    continue
                out.append("sqrt"); c += 1
                continue
            if ch != " " or not any(sub[r][c] != " " for r in range(h)):
                # baseline run (or blank column)
                start = c
                while c < w and (sub[b][c] != " " or not any(sub[r][c] != " " for r in range(h))) and sub[b][c] != "√":
                    c += 1
                    if c < w and sub[b][c] == " " and any(sub[r][c] != " " for r in range(h)):
                        break
                text = "".join(sub[b][start:c])
                out.append(self._baseline_text(text, b, start + off, sub))
                continue
            above = any(sub[r][c] != " " for r in range(b))
            start = c
            while c < w and sub[b][c] == " " and any(sub[r][c] != " " for r in range(h)) and \
                    (any(sub[r][c] != " " for r in range(b)) == above):
                c += 1
            rows = [r[start:c] for r in (sub[:b] if above else sub[b + 1:])]
            inner = self.block(rows)
            if above:
                out.append("**(%s)" % inner)
            else:
                out.append("_" + re.sub(r"\W", "", inner) if inner.replace(" ", "").isalnum() else "[%s]" % inner)
        return "".join(out)

    def _baseline_text(self, text, b, start, sub):
        res = []
        for i, ch in enumerate(text):
            lim = self.ph.get("lim", {}).get((b, start + i)) if isinstance(self.ph.get("lim"), dict) else None
            if ch in self.ph:
                res.append(self.ph[ch])
            elif ch == "∫":
                lo, hi = lim or ("", "")
                res.append("∫[%s;%s]" % (lo, hi))
            elif ch in "∑Σ":
                lo, hi = lim or ("", "")
                res.append("Σ[%s;%s]" % (lo, hi))
            else:
                res.append(ch)
        return "".join(res)

    def inline(self, s):
        out = []
        for ch in s:
            out.append(self.ph.get(ch, ch) if ch != "lim" else ch)
        return "".join(out).strip()


def _join(parts):
    out = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if out and (out[-1].isalnum() or out[-1] == ")") and (p[0].isalnum() or p[0] == "("):
            out += "*"
        elif out and not p.startswith("**") and not p.startswith("_"):
            out += " "
        out += p
    return out


def _bigop_rewrite(s):
    """∫[a;b] f dx -> Integral(f, (x, a, b)) ; Σ[k=1;n] f -> Sum(f, (k, 1, n))."""
    m = re.search(r"∫\[([^;\]]*);([^\]]*)\]\s*(.*?)\s*\*?\s*d\s*\*?\s*([a-zA-Z])\b(.*)$", s)
    if m:
        lo, hi, body, var, rest = m.groups()
        lim = "(%s, %s, %s)" % (var, lo, hi) if lo and hi else var
        return _bigop_rewrite(s[:m.start()] + "Integral(%s, %s)" % (body or "1", lim) + rest)
    m = re.search(r"Σ\[([a-zA-Z]\w*)\s*=\s*([^;\]]*);([^\]]*)\]\s*(.*)$", s)
    if m:
        var, lo, hi, body = m.groups()
        return s[:m.start()] + "Sum(%s, (%s, %s, %s))" % (body, var, lo, hi or "oo")
    return s


def interpret(text):
    """Drawing -> (normalized infix string, sympy object)."""
    it = Interpreter()
    s = it.run(text)
    s = _bigop_rewrite(s)
    s = re.sub(r"\*\*\(([^()]*)\)", lambda m: "**(%s)" % m.group(1), s)
    return s, parse(s)


def render(expr):
    """sympy object or string -> ASCII 2D pretty print."""
    if isinstance(expr, str):
        expr = parse(expr)
    return sp.pretty(expr, use_unicode=False)


def render_unicode(expr):
    if isinstance(expr, str):
        expr = parse(expr)
    return sp.pretty(expr, use_unicode=True)
