"""ChessX math engine: PhD professor mode, ASCII-art equations, step-by-step solving,
math-language export and a safe evaluator. Requires sympy (pip install sympy)."""
from .core import parse, preprocess, MathError
from .professor import Professor, PHD_SYSTEM_PROMPT, set_llm
from .ascii2d import interpret, render

COMMANDS = {"prof": "professor", "professor": "professor", "math": "math",
            "draw": "draw", "render": "render", "pretty": "render",
            "steps": "steps", "check": "check",
            "export": "export", "translate": "translate", "calc": "calc"}
MULTILINE = {"draw", "check", "calc"}          # commands that read a multi-line block from the terminal


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


def _steps(rest, lang, read_block):
    """steps solve|system|diff|integrate|simplify|limit|matrix <input>"""
    from . import steps as st
    kind, _, arg = rest.partition(" ")
    kind = kind.lower()
    fns = {"solve": st.solve_steps, "eq": st.solve_steps, "diff": st.diff_steps, "derive": st.diff_steps,
           "integrate": st.integrate_steps, "int": st.integrate_steps, "simplify": st.simplify_steps,
           "limit": st.limit_steps, "lim": st.limit_steps, "matrix": st.matrix_steps}
    if kind == "system":
        lines = [l for l in arg.split(";") if l.strip()]
        if not lines and read_block:
            print("system: one equation per line, empty line to finish")
            lines = read_block()
        out = st.system_steps(lines)
    elif kind in fns:
        out = fns[kind](arg)
    else:
        return "steps: " + " | ".join(["solve", "system", "diff", "integrate", "simplify", "limit", "matrix"])
    res, n = [], 0
    for l in out:
        if l.startswith("  "):
            res.append("   " + l)
        else:
            n += 1
            res.append("%d. %s" % (n, l))
    return "\n".join(res)


def _check(rest, lang, read_block):
    """check  -> paste your working, one step per line (or separated by ';'), empty line ends."""
    from .steps import check_work
    lines = [l for l in rest.replace(";", "\n").splitlines() if l.strip()]
    if not lines and read_block:
        print("check: paste your working, one step per line, empty line to finish")
        lines = read_block()
    _, report = check_work(lines)
    return "\n".join(report)


def _export(rest, lang, _rb):
    """export <python|numpy|sympy|matlab|octave|julia|r|latex|wolfram|c|all> <expr | solve <equation>>"""
    import sympy as sp
    from .langs import export, export_all
    target, _, expr = rest.partition(" ")
    if not expr.strip():
        return "export <python|numpy|sympy|matlab|octave|julia|r|latex|wolfram|c|all> <expr>"
    obj = None if expr.strip().startswith("solve ") else parse(expr)
    if obj is None or isinstance(obj, sp.Eq):
        e = parse(expr.strip()[6:] if expr.strip().startswith("solve ") else expr)
        e = e if isinstance(e, sp.Eq) else sp.Eq(e, 0)
        x = sorted(e.free_symbols, key=str)[0]
        obj = sp.solve(e, x)
    return export_all(obj) if target.lower() == "all" else export(obj, target)


def _translate(rest, lang, _rb):
    """translate <from> <to> <code>   e.g. translate wolfram python Sin[x]^2"""
    from .langs import translate
    parts = rest.split(None, 2)
    if len(parts) < 3:
        return "translate <from> <to> <expr>  (python numpy matlab octave julia r latex wolfram c)"
    return translate(parts[2], parts[0], parts[1])


def _calc(rest, lang, read_block):
    """calc a = 3; b = a^2 + 1; sqrt(b)   (or 'calc' alone for a multi-line snippet)"""
    from .langs import safe_eval
    text = rest
    if not text.strip() and read_block:
        print("calc: one statement per line, empty line to finish")
        text = "\n".join(read_block())
    return "\n".join(safe_eval(text))


_HANDLERS = {"professor": _professor, "math": _math, "draw": _draw, "render": _render,
             "steps": _steps, "check": _check, "export": _export, "translate": _translate, "calc": _calc}
__all__ = ["parse", "preprocess", "MathError", "Professor", "PHD_SYSTEM_PROMPT", "set_llm", "dispatch",
           "is_math_command", "COMMANDS", "interpret", "render"]
