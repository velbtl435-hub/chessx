"""ChessX math engine: PhD professor mode, ASCII-art equations, step-by-step solving,
math-language export and a safe evaluator. Requires sympy (pip install sympy)."""
from .core import parse, preprocess, MathError
from .professor import Professor, PHD_SYSTEM_PROMPT, set_llm
from .ascii2d import interpret, render

COMMANDS = {"prof": "professor", "professor": "professor", "math": "math",
            "draw": "draw", "render": "render", "pretty": "render"}
MULTILINE = {"draw"}          # commands that read a multi-line block from the terminal


def _head(text):
    parts = (text or "").strip().split(None, 1)
    return (parts[0].lower() if parts else ""), (parts[1] if len(parts) > 1 else "")


def is_math_command(text):
    return _head(text)[0] in COMMANDS


def dispatch(text, lang="en", read_block=None):
    """Run a math shell command. read_block() returns the lines of a multi-line block."""
    head, rest = _head(text)
    kind = COMMANDS[head]
    try:
        return _HANDLERS[kind](rest if kind in MULTILINE else rest.strip(), lang, read_block)
    except MathError as e:
        return "math error: %s" % e
    except Exception as e:  # sympy can raise many things; report, never crash the shell
        return "math error: %s: %s" % (type(e).__name__, e)


def _professor(rest, lang, _rb):
    return Professor(lang).ask(rest)


def _math(rest, lang, _rb):
    import sympy as sp
    e = parse(rest)
    if isinstance(e, sp.Eq):
        return Professor(lang).t_solve(rest)
    v = sp.simplify(e)
    out = "%s = %s" % (sp.sstr(e), sp.sstr(v))
    if getattr(v, "is_number", False) and not v.is_Integer:
        out += " ≈ %s" % sp.N(v, 12)
    return out


def _draw(rest, lang, read_block):
    """draw  -> type the equation on several lines, finish with an empty line."""
    import sympy as sp
    from .ascii2d import interpret, render
    text = rest
    if not text.strip("\n ") and read_block:
        print("draw: type your equation (ASCII art), empty line to finish")
        text = "\n".join(read_block())
    s, e = interpret(text)
    out = ["expr  : " + s, "sympy : " + sp.sstr(e), render(e)]
    try:
        if isinstance(e, sp.Eq):
            x = sorted(e.free_symbols, key=str)
            out.append("solve : %s = %s" % (x[0], sp.solve(e, x[0])) if x else "")
        elif not isinstance(e, sp.MatrixBase):
            v = e.doit() if hasattr(e, "doit") else e
            v = sp.simplify(v)
            if v != e:
                out.append("value : " + sp.sstr(v))
    except Exception:
        pass
    return "\n".join(out)


def _render(rest, lang, _rb):
    from .ascii2d import render
    return render(rest)


_HANDLERS = {"professor": _professor, "math": _math, "draw": _draw, "render": _render}
__all__ = ["parse", "preprocess", "MathError", "Professor", "PHD_SYSTEM_PROMPT", "set_llm", "dispatch",
           "is_math_command", "COMMANDS", "interpret", "render"]
