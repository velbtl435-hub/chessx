"""Mathematical programming languages: export / translate expressions between notations
and a sandboxed numeric evaluator (no eval/exec: everything goes through core.parse's AST whitelist).
"""
import re
import signal
import threading

import sympy as sp
from sympy.printing.numpy import NumPyPrinter

from .core import parse, MathError

LANGS = ("python", "numpy", "sympy", "matlab", "octave", "julia", "r", "latex", "wolfram", "mathematica", "c")


def export(expr, lang):
    """Render a sympy object (or text) as code in the target language."""
    if isinstance(expr, str):
        expr = parse(expr)
    lang = lang.lower()
    if isinstance(expr, list) and expr and all(isinstance(r, list) for r in expr):
        expr = sp.Matrix(expr)
    if isinstance(expr, list):
        return "[" + ", ".join(export(e, lang) for e in expr) + "]"
    if lang == "python":
        return sp.pycode(expr, fully_qualified_modules=True)
    if lang == "numpy":
        return NumPyPrinter({"fully_qualified_modules": True}).doprint(expr)
    if lang == "sympy":
        return sp.python(expr).replace("e = ", "expr = ")
    if lang in ("matlab", "octave"):
        return sp.octave_code(expr)
    if lang == "julia":
        return sp.julia_code(expr)
    if lang == "r":
        if isinstance(expr, sp.MatrixBase):
            return "matrix(c(%s), nrow=%d, byrow=TRUE)" % (", ".join(sp.rcode(v) for v in expr), expr.rows)
        return sp.rcode(expr)
    if lang == "latex":
        return sp.latex(expr)
    if lang in ("wolfram", "mathematica"):
        return sp.mathematica_code(expr)
    if lang == "c":
        if isinstance(expr, sp.MatrixBase):
            return "{" + ", ".join("{" + ", ".join(sp.ccode(v) for v in expr.row(i)) + "}" for i in range(expr.rows)) + "}"
        return sp.ccode(expr, standard="C99")
    raise MathError("unknown language %r (use %s)" % (lang, ", ".join(LANGS)))


def export_all(expr):
    if isinstance(expr, str):
        expr = parse(expr)
    if isinstance(expr, list) and expr and all(isinstance(r, list) for r in expr):
        expr = sp.Matrix(expr)
    out = []
    for lang in ("python", "numpy", "matlab", "julia", "r", "latex", "wolfram", "c"):
        try:
            out.append("%-8s %s" % (lang + ":", export(expr, lang)))
        except Exception as e:
            out.append("%-8s (n/a: %s)" % (lang + ":", e))
    return "\n".join(out)


# ------------------------------------------------------------ importing
_WOLFRAM_FUNCS = {"Sin": "sin", "Cos": "cos", "Tan": "tan", "Exp": "exp", "Log": "log", "Sqrt": "sqrt",
                  "ArcTan": "atan", "ArcSin": "asin", "ArcCos": "acos", "Abs": "abs", "Pi": "pi", "E": "E"}


def from_notation(text, lang):
    """Read an expression written in another notation (MATLAB/Octave/Julia/R/Wolfram/C/Python/LaTeX-lite)."""
    s = text.strip().rstrip(";")
    lang = lang.lower()
    if lang in ("matlab", "octave", "julia", "r"):
        s = s.replace(".^", "^").replace(".*", "*").replace("./", "/")
        s = re.sub(r"\[([^\]]*;[^\]]*)\]", lambda m: "[" + ",".join("[%s]" % ",".join(r.split()) if "," not in r else "[%s]" % r
                                                                   for r in m.group(1).split(";")) + "]", s)
        if lang == "julia":
            s = s.replace("√", "sqrt")
    elif lang in ("wolfram", "mathematica"):
        s = re.sub(r"\b([A-Z][a-zA-Z]*)\[", lambda m: _WOLFRAM_FUNCS.get(m.group(1), m.group(1)) + "(", s)
        s = s.replace("]", ")")
        s = re.sub(r"\bPi\b", "pi", s)
    elif lang == "c":
        s = re.sub(r"\bpow\(", "Pow__(", s)
        s = re.sub(r"Pow__\(([^,]+),([^)]+)\)", r"((\1)**(\2))", s)
        s = s.replace("M_PI", "pi").replace("fabs", "abs")
    elif lang in ("python", "numpy", "sympy"):
        s = re.sub(r"\b(?:np|numpy|math|sympy|sp)\.", "", s).replace("math.pi", "pi")
    elif lang == "latex":
        s = _latex_lite(s)
    else:
        raise MathError("unknown language %r" % lang)
    return parse(s)


def _latex_lite(s):
    s = s.replace("\\left", "").replace("\\right", "").replace("\\cdot", "*").replace("\\times", "*")
    for _ in range(6):
        s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", s)
        s = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", s)
        s = re.sub(r"\^\{([^{}]*)\}", r"**(\1)", s)
    s = re.sub(r"\\(sin|cos|tan|exp|ln|log|pi)\b", r"\1", s)
    return s.replace("{", "(").replace("}", ")")


def translate(text, src, dst):
    return export(from_notation(text, src), dst)


# --------------------------------------------------------- sandboxed eval
class _Timeout(Exception):
    pass


def _with_timeout(fn, seconds):
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
        return fn()
    def handler(*_):
        raise _Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def safe_eval(snippet, timeout=3.0, max_statements=50):
    """Evaluate small numeric snippets:  'a = 3; b = a^2 + 1; sqrt(b)'.
    Statements separated by ';' or newlines; 'name = expr' assigns. Only the math AST whitelist is accepted
    (no attributes, subscripts, imports, lambdas, strings, comprehensions...). Returns list of 'line -> value'."""
    stmts = [s.strip() for s in re.split(r"[;\n]", snippet) if s.strip() and not s.strip().startswith("#")]
    if len(stmts) > max_statements:
        raise MathError("too many statements")
    env, out = {}, []

    def run():
        for st in stmts:
            m = re.fullmatch(r"([A-Za-z]\w*)\s*=(?!=)\s*(.+)", st)
            if m and not m.group(1).startswith("_"):
                v = parse(m.group(2), env, allow_eq=False)
                env[m.group(1)] = v
                out.append("%s = %s" % (m.group(1), _num(v)))
            else:
                out.append("%s -> %s" % (st, _num(parse(st, env))))
    try:
        _with_timeout(run, timeout)
    except _Timeout:
        raise MathError("timed out after %gs" % timeout)
    return out


def _num(v):
    if isinstance(v, list):
        return "[" + ", ".join(_num(x) for x in v) + "]"
    if isinstance(v, sp.MatrixBase):
        return sp.sstr(v.evalf(12))
    if isinstance(v, sp.Basic) and v.is_number:
        exact = sp.nsimplify(v) if v.is_Float else v
        n = sp.N(v, 12)
        return sp.sstr(exact) if exact == n or exact.is_Integer else "%s ≈ %s" % (sp.sstr(v), sp.sstr(n))
    return sp.sstr(v)
