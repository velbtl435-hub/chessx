"""Safe expression parsing for the ChessX math engine.

Text is converted to a sympy expression by walking a whitelisted Python AST.
Nothing is ever passed to eval/exec, so input like __import__('os') is rejected.
"""
import ast
import re

import sympy as sp

FUNCS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "exp": sp.exp, "log": sp.log, "ln": sp.log,
    "sqrt": sp.sqrt, "abs": sp.Abs, "Abs": sp.Abs, "factorial": sp.factorial, "floor": sp.floor,
    "ceiling": sp.ceiling, "gamma": sp.gamma, "Heaviside": sp.Heaviside, "re": sp.re, "im": sp.im,
    "conjugate": sp.conjugate, "arg": sp.arg, "binomial": sp.binomial, "Matrix": sp.Matrix,
    "diff": sp.diff, "integrate": sp.integrate, "limit": sp.limit, "Derivative": sp.Derivative,
    "Integral": sp.Integral, "Sum": sp.Sum, "Function": sp.Function, "gcd": sp.gcd, "lcm": sp.lcm,
    "Eq": sp.Eq, "simplify": sp.simplify, "expand": sp.expand, "factor": sp.factor, "Rational": sp.Rational,
}
CONSTS = {"pi": sp.pi, "e": sp.E, "E": sp.E, "I": sp.I, "j": sp.I, "oo": sp.oo, "inf": sp.oo,
          "True": sp.true, "False": sp.false}
MAX_LEN = 2000
MAX_POW = 10000

_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Mod: lambda a, b: sp.Mod(a, b), ast.FloorDiv: lambda a, b: sp.floor(a / b),
        ast.MatMult: lambda a, b: a * b}
_CMP = {ast.Lt: sp.Lt, ast.LtE: sp.Le, ast.Gt: sp.Gt, ast.GtE: sp.Ge, ast.Eq: sp.Eq, ast.NotEq: sp.Ne}


class MathError(ValueError):
    pass


def preprocess(text):
    """Normalise human notation: ^ -> **, unicode symbols, implicit multiplication (2x, 3(x+1), )(  )."""
    s = text.strip()
    for a, b in (("^", "**"), ("×", "*"), ("·", "*"), ("÷", "/"), ("−", "-"), ("√", "sqrt"), ("π", "pi"),
                 ("∞", "oo"), ("²", "**2"), ("³", "**3"), ("≤", "<="), ("≥", ">="), ("≠", "!=")):
        s = s.replace(a, b)
    s = re.sub(r"(?<![\w.])(\d+(?:\.\d*)?)(?![eE][+-]?\d)\s*([a-zA-Z_(])", r"\1*\2", s)  # 2x, 3(x+1); keeps 2e3, log10
    s = re.sub(r"\)\s*([a-zA-Z0-9(])", r")*\1", s)          # )(  )x
    return s


def _split_eq(s):
    """Return (lhs, rhs) if s has a single '=' that is not part of ==, <=, >=, !=."""
    parts = re.split(r"(?<![=<>!])=(?!=)", s)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None


def parse(text, symbols=None, allow_eq=True):
    """Parse text into a sympy object. 'a = b' becomes Eq(a, b)."""
    if len(text) > MAX_LEN:
        raise MathError("expression too long")
    s = preprocess(text)
    if allow_eq:
        eq = _split_eq(s)
        if eq:
            return sp.Eq(parse(eq[0], symbols, False), parse(eq[1], symbols, False))
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as e:
        raise MathError("syntax error: %s" % e.msg)
    syms = dict(symbols or {})
    return _walk(tree.body, syms)


def _walk(n, syms):
    w = lambda x: _walk(x, syms)
    if isinstance(n, ast.Constant):
        if isinstance(n.value, bool):
            return sp.true if n.value else sp.false
        if isinstance(n.value, (int, float)):
            return sp.nsimplify(n.value) if isinstance(n.value, float) else sp.Integer(n.value)
        if isinstance(n.value, complex):
            return sp.I * sp.nsimplify(n.value.imag)
        raise MathError("strings are not allowed")
    if isinstance(n, ast.Name):
        if n.id.startswith("_"):
            raise MathError("name not allowed: " + n.id)
        if n.id in syms:
            return syms[n.id]
        if n.id in CONSTS:
            return CONSTS[n.id]
        if n.id in FUNCS:
            return FUNCS[n.id]
        syms[n.id] = sp.Symbol(n.id)
        return syms[n.id]
    if isinstance(n, ast.BinOp):
        if isinstance(n.op, ast.Pow):
            b, e = w(n.left), w(n.right)
            if e.is_number and e.is_real and abs(e) > MAX_POW:
                raise MathError("exponent too large")
            return b ** e
        if isinstance(n.op, ast.BitXor):
            return w(n.left) ** w(n.right)
        if isinstance(n.op, ast.BitAnd):
            return sp.And(w(n.left), w(n.right))
        if isinstance(n.op, ast.BitOr):
            return sp.Or(w(n.left), w(n.right))
        op = _BIN.get(type(n.op))
        if not op:
            raise MathError("operator not allowed")
        return op(w(n.left), w(n.right))
    if isinstance(n, ast.UnaryOp):
        v = w(n.operand)
        if isinstance(n.op, ast.USub):
            return -v
        if isinstance(n.op, ast.UAdd):
            return v
        if isinstance(n.op, (ast.Not, ast.Invert)):
            return sp.Not(v)
    if isinstance(n, ast.BoolOp):
        vals = [w(v) for v in n.values]
        return sp.And(*vals) if isinstance(n.op, ast.And) else sp.Or(*vals)
    if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _CMP:
        return _CMP[type(n.ops[0])](w(n.left), w(n.comparators[0]))
    if isinstance(n, (ast.List, ast.Tuple)):
        return [w(x) for x in n.elts]
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
        name = n.func.id
        f = FUNCS.get(name)
        args = [w(a) for a in n.args]
        if f is None:
            if name.startswith("_") or name in CONSTS:
                raise MathError("function not allowed: " + name)
            return sp.Function(name)(*args)          # undefined function f(x), y(t)
        if name == "Matrix":
            return sp.Matrix(*args)
        return f(*args)
    raise MathError("construct not allowed: " + type(n).__name__)


def to_str(x):
    s = sp.sstr(x)
    return s
