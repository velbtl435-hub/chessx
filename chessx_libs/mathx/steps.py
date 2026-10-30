"""Step-by-step solutions and 'check my calculation'.

Every function returns a list of human-readable steps (strings); the last one is the answer.
"""
import sympy as sp

from .core import parse, MathError


def _var(e, prefer="x"):
    syms = sorted(e.free_symbols, key=str)
    for s in syms:
        if str(s) == prefer:
            return s
    if not syms:
        raise MathError("no variable")
    return syms[0]


def S(e):
    return sp.sstr(e)


# ------------------------------------------------------------------ equations
def solve_steps(text):
    e = parse(text)
    eq = e if isinstance(e, sp.Eq) else sp.Eq(e, 0)
    x = _var(eq)
    expr = sp.expand(eq.lhs - eq.rhs)
    steps = ["Equation: %s = %s" % (S(eq.lhs), S(eq.rhs)), "Move everything to one side: %s = 0" % S(expr)]
    num, den = sp.fraction(sp.together(expr))
    if den.has(x):
        steps.append("Multiply by the denominator %s (≠ 0): %s = 0" % (S(den), S(sp.expand(num))))
        expr = sp.expand(num)
    poly = sp.Poly(expr, x) if expr.is_polynomial(x) else None
    if poly and poly.degree() == 1:
        a, b = poly.all_coeffs()
        steps += ["Linear: a·%s + b = 0 with a = %s, b = %s" % (x, S(a), S(b)),
                  "Subtract b: %s·%s = %s" % (S(a), x, S(-b)),
                  "Divide by a: %s = %s" % (x, S(sp.nsimplify(-b / a)))]
        sols = [sp.nsimplify(-b / a)]
    elif poly and poly.degree() == 2:
        a, b, c = poly.all_coeffs()
        D = sp.simplify(b ** 2 - 4 * a * c)
        steps += ["Quadratic: a = %s, b = %s, c = %s" % (S(a), S(b), S(c)),
                  "Discriminant Δ = b² - 4ac = %s" % S(D),
                  ("Δ > 0: two real roots" if D.is_positive else "Δ = 0: one double root" if D == 0
                   else "Δ < 0: complex conjugate roots" if D.is_negative else "Δ symbolic"),
                  "x = (-b ± √Δ) / (2a)"]
        sols = [sp.simplify((-b + sp.sqrt(D)) / (2 * a)), sp.simplify((-b - sp.sqrt(D)) / (2 * a))]
        steps.append("%s₁ = %s,  %s₂ = %s" % (x, S(sols[0]), x, S(sols[1])))
        f = sp.factor(expr)
        if f != expr:
            steps.append("Check by factoring: %s = 0" % S(f))
    else:
        f = sp.factor(expr)
        if f != expr:
            steps.append("Factor: %s = 0 → each factor = 0" % S(f))
        sols = sp.solve(expr, x)
    if den.has(x):
        bad = [s for s in sols if sp.simplify(den.subs(x, s)) == 0]
        if bad:
            steps.append("Discard %s (makes the denominator zero)" % bad)
        sols = [s for s in sols if s not in bad]
    sols = list(dict.fromkeys(sols))
    steps.append("Solution: %s = %s" % (x, S(sols[0]) if len(sols) == 1 else S(sols)))
    return steps


def system_steps(lines):
    """lines: ['2x + y = 5', 'x - y = 1'] -> Gauss-Jordan elimination on the augmented matrix."""
    eqs = [parse(l) for l in lines if l.strip()]
    eqs = [q if isinstance(q, sp.Eq) else sp.Eq(q, 0) for q in eqs]
    syms = sorted(set().union(*[q.free_symbols for q in eqs]), key=str)
    A, b = sp.linear_eq_to_matrix([q.lhs - q.rhs for q in eqs], syms)
    M = A.row_join(b)
    steps = ["Unknowns: %s" % syms, "Augmented matrix [A|b] = %s" % M.tolist()]
    rows, cols = A.shape
    r = 0
    for c in range(cols):
        piv = next((i for i in range(r, rows) if M[i, c] != 0), None)
        if piv is None:
            continue
        if piv != r:
            M = M.elementary_row_op("n<->m", row1=r, row2=piv)
            steps.append("R%d ↔ R%d → %s" % (r + 1, piv + 1, M.tolist()))
        if M[r, c] != 1:
            k = M[r, c]
            M = M.elementary_row_op("n->kn", row=r, k=1 / k)
            steps.append("R%d ← R%d / %s → %s" % (r + 1, r + 1, S(k), M.tolist()))
        for i in range(rows):
            if i != r and M[i, c] != 0:
                k = M[i, c]
                M = M.elementary_row_op("n->n+km", row=i, k=-k, row2=r)
                steps.append("R%d ← R%d - (%s)·R%d → %s" % (i + 1, i + 1, S(k), r + 1, M.tolist()))
        r += 1
        if r == rows:
            break
    sol = sp.linsolve((A, b), syms)
    steps.append("Solution: %s" % (dict(zip(syms, list(sol)[0])) if sol else "no solution (inconsistent)"))
    return steps


# ----------------------------------------------------------------- derivative
def _d(e, x, out, depth=0):
    """Differentiate recursively, recording the rule used at each node."""
    pad = "  " * depth
    if not e.has(x):
        out.append(pad + "constant rule: d/d%s[%s] = 0" % (x, S(e)))
        return sp.Integer(0)
    if e == x:
        out.append(pad + "d/d%s[%s] = 1" % (x, x))
        return sp.Integer(1)
    if e.is_Add:
        out.append(pad + "sum rule: d[%s] = %s" % (S(e), " + ".join("d[%s]" % S(t) for t in e.args)))
        return sp.Add(*[_d(t, x, out, depth + 1) for t in e.args])
    if e.is_Mul:
        c, rest = e.as_independent(x)
        if c != 1:
            out.append(pad + "constant multiple: d[%s·%s] = %s·d[%s]" % (S(c), S(rest), S(c), S(rest)))
            return c * _d(rest, x, out, depth + 1)
        num, den = sp.fraction(e)
        if den != 1 and den.has(x):
            out.append(pad + "quotient rule: (u/v)' = (u'v - uv')/v², u = %s, v = %s" % (S(num), S(den)))
            du, dv = _d(num, x, out, depth + 1), _d(den, x, out, depth + 1)
            return (du * den - num * dv) / den ** 2
        u, v = e.args[0], sp.Mul(*e.args[1:])
        out.append(pad + "product rule: (uv)' = u'v + uv', u = %s, v = %s" % (S(u), S(v)))
        du, dv = _d(u, x, out, depth + 1), _d(v, x, out, depth + 1)
        return du * v + u * dv
    if e.is_Pow:
        b, n = e.args
        if not n.has(x):
            if b == x:
                out.append(pad + "power rule: d[%s^%s] = %s·%s^%s" % (x, S(n), S(n), x, S(n - 1)))
                return n * x ** (n - 1)
            out.append(pad + "chain + power rule: d[u^%s] = %s·u^%s·u', u = %s" % (S(n), S(n), S(n - 1), S(b)))
            return n * b ** (n - 1) * _d(b, x, out, depth + 1)
        if not b.has(x):
            out.append(pad + "exponential rule: d[a^u] = a^u·ln(a)·u', a = %s, u = %s" % (S(b), S(n)))
            return e * sp.log(b) * _d(n, x, out, depth + 1)
        out.append(pad + "logarithmic differentiation: d[u^v] = u^v·(v'ln u + v u'/u)")
        return sp.diff(e, x)
    if isinstance(e, sp.exp):
        u = e.args[0]
        out.append(pad + ("d[e^x] = e^x" if u == x else "chain rule: d[e^u] = e^u·u', u = %s" % S(u)))
        return e * (1 if u == x else _d(u, x, out, depth + 1))
    table = {sp.sin: (sp.cos, "cos(u)"), sp.cos: (lambda u: -sp.sin(u), "-sin(u)"), sp.tan: (lambda u: 1 / sp.cos(u) ** 2, "sec²(u)"),
             sp.log: (lambda u: 1 / u, "1/u"), sp.asin: (lambda u: 1 / sp.sqrt(1 - u ** 2), "1/√(1-u²)"),
             sp.atan: (lambda u: 1 / (1 + u ** 2), "1/(1+u²)"), sp.sinh: (sp.cosh, "cosh(u)"), sp.cosh: (sp.sinh, "sinh(u)")}
    if e.func in table and len(e.args) == 1:
        f, txt = table[e.func]
        u = e.args[0]
        name = e.func.__name__
        if u == x:
            out.append(pad + "d[%s(%s)] = %s" % (name, x, txt.replace("u", str(x))))
            return f(u)
        out.append(pad + "chain rule: d[%s(u)] = %s·u', u = %s" % (name, txt, S(u)))
        return f(u) * _d(u, x, out, depth + 1)
    out.append(pad + "general rule (sympy): d[%s]" % S(e))
    return sp.diff(e, x)


def diff_steps(text, var=None):
    e = parse(text)
    x = sp.Symbol(var) if var else _var(e)
    out = ["f(%s) = %s" % (x, S(e))]
    r = _d(e, x, out)
    simp = sp.simplify(r)
    assert sp.simplify(simp - sp.diff(e, x)) == 0
    out.append("Collect: f'(%s) = %s" % (x, S(simp)))
    return out


# ------------------------------------------------------------------- integral
def integrate_steps(text, var=None):
    from sympy.integrals.manualintegrate import integral_steps
    e = parse(text)
    x = sp.Symbol(var) if var else _var(e)
    out = ["∫ %s d%s" % (S(e), x)]

    def walk(rule, depth):
        name = type(rule).__name__.replace("Rule", "")
        pad = "  " * depth
        integrand = getattr(rule, "integrand", None)
        desc = {"Add": "linearity: integrate term by term", "ConstantTimes": "pull the constant out",
                "Power": "power rule: ∫x^n dx = x^(n+1)/(n+1)", "Exp": "∫e^u du = e^u", "Constant": "∫c dx = c·x",
                "URule": "substitution u = g(x)", "U": "substitution", "Parts": "integration by parts: ∫u dv = uv - ∫v du",
                "Sin": "∫sin = -cos", "Cos": "∫cos = sin", "Reciprocal": "∫1/x dx = ln|x|", "Rewrite": "rewrite the integrand",
                "PartsRule": "by parts", "Trig": "trigonometric rule", "Alternative": "choose a method", "Arctan": "∫1/(1+x²) = atan"}
        extra = ""
        if name == "U":
            extra = " with u = %s" % S(rule.u_func)
        if name == "Parts":
            extra = " with u = %s, dv = %s" % (S(rule.u), S(rule.dv))
        out.append("%s%s: %s%s" % (pad, S(integrand) if integrand is not None else "", desc.get(name, name), extra))
        for attr in ("substeps", "substep", "v_step", "second_step", "rewritten_step", "alternatives"):
            sub = getattr(rule, attr, None)
            if sub is None:
                continue
            for s in (sub if isinstance(sub, (list, tuple)) else [sub]):
                if hasattr(s, "integrand"):
                    walk(s, depth + 1)
                if attr == "alternatives":
                    break

    try:
        walk(integral_steps(e, x), 1)
    except Exception:
        out.append("  (no elementary manual rule; using the Risch/heuristic algorithm)")
    out.append("Result: %s + C" % S(sp.integrate(e, x)))
    return out


# ---------------------------------------------------------------- simplify
def simplify_steps(text):
    e = parse(text)
    out = ["Start: %s" % S(e)]
    cur = e
    for name, fn in (("expand", sp.expand), ("cancel common factors", sp.cancel), ("factor", sp.factor),
                     ("trigonometric identities", sp.trigsimp), ("combine powers", sp.powsimp), ("simplify", sp.simplify)):
        nxt = fn(cur)
        if nxt != cur and sp.count_ops(nxt) <= sp.count_ops(cur) + (1 if name == "expand" else 0):
            out.append("%s → %s" % (name, S(nxt)))
            cur = nxt
    out.append("Result: %s" % S(cur))
    return out


# ------------------------------------------------------------------- limits
def limit_steps(text):
    expr, _, to = text.partition("->")
    e = parse(expr)
    x = _var(e)
    p = parse(to) if to.strip() else sp.Integer(0)
    out = ["lim %s→%s  %s" % (x, S(p), S(e))]
    num, den = sp.fraction(sp.together(e))
    try:
        direct = sp.simplify(e.subs(x, p)) if p not in (sp.oo, -sp.oo) else None
    except Exception:
        direct = None
    if direct is not None and direct.is_finite and direct is not sp.nan:
        out.append("Direct substitution: %s" % S(direct))
        out.append("Result: %s" % S(direct))
        return out
    n0, d0 = sp.limit(num, x, p), sp.limit(den, x, p)
    out.append("Substitution gives %s/%s" % (S(n0), S(d0)))
    k = 0
    while ((n0 == 0 and d0 == 0) or (abs(n0) == sp.oo and abs(d0) == sp.oo)) and k < 4:
        f = sp.cancel(num / den)
        if f != num / den and k == 0:
            out.append("Indeterminate form → cancel common factors: %s" % S(f))
            nf, df = sp.fraction(f)
            if sp.limit(df, x, p) != 0:
                num, den = nf, df
                break
        num, den = sp.diff(num, x), sp.diff(den, x)
        out.append("Indeterminate form → L'Hôpital: f'/g' = (%s)/(%s)" % (S(num), S(den)))
        n0, d0 = sp.limit(num, x, p), sp.limit(den, x, p)
        k += 1
    res = sp.limit(e, x, p)
    out.append("Result: %s" % S(res))
    return out


# --------------------------------------------------------------- matrices
def matrix_steps(text):
    """'det [[1,2],[3,4]]' | 'inv [[..]]' | 'mul [[..]] [[..]]' | 'transpose ..' | 'eig ..'."""
    op, _, rest = text.strip().partition(" ")
    op = op.lower()
    if op in ("mul", "multiply"):
        a, b = _two_matrices(rest)
        out = ["A·B: (A·B)ij = Σk Aik·Bkj"]
        C = a * b
        for i in range(C.rows):
            for j in range(C.cols):
                terms = " + ".join("%s·%s" % (S(a[i, k]), S(b[k, j])) for k in range(a.cols))
                out.append("c%d%d = %s = %s" % (i + 1, j + 1, terms, S(C[i, j])))
        out.append("Result: %s" % C.tolist())
        return out
    M = sp.Matrix(parse(rest))
    if op == "det":
        out = ["det of %s" % M.tolist()]
        if M.shape == (2, 2):
            out.append("2×2: ad - bc = %s·%s - %s·%s" % (S(M[0, 0]), S(M[1, 1]), S(M[0, 1]), S(M[1, 0])))
        else:
            terms = ["(%s)·(%s)·det(M1%d)" % ("+" if j % 2 == 0 else "-", S(M[0, j]), j + 1) for j in range(M.cols)]
            out.append("Laplace (cofactor) expansion along row 1: " + " ".join(terms))
            for j in range(M.cols):
                out.append("  det(M1%d) = %s" % (j + 1, S(M.minor_submatrix(0, j).det())))
        out.append("Result: det = %s" % S(M.det()))
        return out
    if op in ("inv", "inverse"):
        d = M.det()
        out = ["det = %s" % S(d)]
        if d == 0:
            return out + ["Result: singular matrix, no inverse"]
        out.append("cofactor matrix C = %s" % M.cofactor_matrix().tolist())
        out.append("adj(A) = Cᵀ = %s" % M.adjugate().tolist())
        out.append("A⁻¹ = adj(A)/det")
        out.append("Result: %s" % M.inv().tolist())
        return out
    if op in ("t", "transpose"):
        return ["Swap rows and columns: (Aᵀ)ij = Aji", "Result: %s" % M.T.tolist()]
    if op in ("eig", "eigen"):
        lam = sp.Symbol("lambda")
        p = sp.factor((M - lam * sp.eye(M.rows)).det())
        return ["Characteristic polynomial det(A - λI) = %s" % S(p), "Roots λ = %s" % S(sp.solve(p, lam)),
                "Result: eigenvectors %s" % [(S(v), m, [S(x.T) for x in vs]) for v, m, vs in M.eigenvects()]]
    raise MathError("matrix op: det | inv | mul | transpose | eig")


def _two_matrices(rest):
    depth = 0
    for i, ch in enumerate(rest):
        depth += ch == "["
        depth -= ch == "]"
        if depth == 0 and ch == "]":
            return sp.Matrix(parse(rest[:i + 1])), sp.Matrix(parse(rest[i + 1:].strip()))
    raise MathError("need two matrices")


# ------------------------------------------------------- check my working
def check_work(lines):
    """Each line is a step of the user's working. Consecutive steps must be equivalent:
    expressions must be equal; equations must have the same solution set.
    Returns (index_of_first_wrong_line or None, report_lines)."""
    steps = [l.strip().lstrip("=⇒→").strip() for l in lines if l.strip()]
    steps = [s for s in steps if s]
    report = []
    prev = None
    for i, s in enumerate(steps):
        try:
            cur = parse(s)
        except MathError as e:
            report.append("✗ line %d: cannot read '%s' (%s)" % (i + 1, s, e))
            return i, report
        if prev is not None:
            ok = _equivalent(prev, cur)
            if not ok:
                report.append("✗ line %d is WRONG: '%s' does not follow from '%s'" % (i + 1, s, steps[i - 1]))
                hint = _hint(prev, cur)
                if hint:
                    report.append("  hint: " + hint)
                return i, report
            report.append("✓ line %d: %s" % (i + 1, s))
        else:
            report.append("  line 1: %s" % s)
        prev = cur
    report.append("All steps are consistent.")
    return None, report


def _equivalent(a, b):
    if isinstance(a, sp.Eq) != isinstance(b, sp.Eq):
        if isinstance(a, sp.Eq) and len(a.free_symbols) == 0:
            return False
        if isinstance(a, sp.Eq) and isinstance(b, sp.Basic):
            return False
        return False
    if isinstance(a, sp.Eq):
        syms = sorted(a.free_symbols | b.free_symbols, key=str)
        if len(syms) == 1:
            x = syms[0]
            sa = set(sp.solveset(a.lhs - a.rhs, x, sp.S.Complexes)) if True else set()
            sb = set(sp.solveset(b.lhs - b.rhs, x, sp.S.Complexes))
            return {sp.nsimplify(v) for v in sa} == {sp.nsimplify(v) for v in sb}
        # multivariable: equal up to a non-zero constant factor
        da, db = sp.expand(a.lhs - a.rhs), sp.expand(b.lhs - b.rhs)
        if db == 0:
            return da == 0
        r = sp.simplify(da / db)
        return r.is_number and r != 0
    return sp.simplify(a - b) == 0


def _hint(a, b):
    try:
        if isinstance(a, sp.Eq) and isinstance(b, sp.Eq):
            x = sorted(a.free_symbols | b.free_symbols, key=str)[0]
            return "expected solutions %s, your line gives %s" % (S(sp.solve(a, x)), S(sp.solve(b, x)))
        d = sp.simplify(b - a)
        return "your line differs from the previous by %s" % S(d)
    except Exception:
        return ""
