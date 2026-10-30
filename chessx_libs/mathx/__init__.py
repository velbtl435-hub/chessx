"""ChessX math engine: PhD professor mode, ASCII-art equations, step-by-step solving,
math-language export and a safe evaluator. Requires sympy (pip install sympy)."""
from .core import parse, preprocess, MathError
from .professor import Professor, PHD_SYSTEM_PROMPT, set_llm

COMMANDS = {"prof": "professor", "professor": "professor", "math": "math"}
MULTILINE = set()          # commands that read a multi-line block from the terminal


def is_math_command(text):
    return (text or "").strip().split(" ", 1)[0].lower() in COMMANDS


def dispatch(text, lang="en", read_block=None):
    """Run a math shell command. read_block() returns the lines of a multi-line block."""
    head, _, rest = text.strip().partition(" ")
    kind = COMMANDS[head.lower()]
    try:
        return _HANDLERS[kind](rest.strip(), lang, read_block)
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


_HANDLERS = {"professor": _professor, "math": _math}
__all__ = ["parse", "preprocess", "MathError", "Professor", "PHD_SYSTEM_PROMPT", "set_llm", "dispatch",
           "is_math_command", "COMMANDS"]
