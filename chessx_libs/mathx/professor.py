"""'PhD professor' mode: deterministic, offline solvers + explanations across
mathematics, electrical engineering, computing, software and systems analysis.

Usage from the shell:  prof <topic> <args>   e.g.  prof ohm V=12 R=4
An optional LLM backend can be plugged with set_llm(callable(system, user) -> str);
it is only used for free-form questions no deterministic solver covers.
"""
import cmath
import math
import re
import statistics

import sympy as sp

from .core import parse, MathError

PHD_SYSTEM_PROMPT = (
    "You are a multidisciplinary PhD professor (mathematics, electrical engineering, computer science, "
    "software engineering, systems analysis). Answer rigorously, state assumptions and units, show the "
    "derivation step by step, give the governing formula first, then the numeric result, then intuition "
    "and a common pitfall. Reply in the user's language.")

_LLM = None


def set_llm(fn):
    """Register fn(system_prompt, question) -> str. Pass None to disable."""
    global _LLM
    _LLM = fn


_PREFIX = {"T": 1e12, "G": 1e9, "M": 1e6, "k": 1e3, "K": 1e3, "m": 1e-3, "u": 1e-6, "µ": 1e-6, "n": 1e-9, "p": 1e-12}


def si(v):
    """'4k7' -> 4700, '1u' -> 1e-6, '10m' -> 0.01, '2.2e-3' -> 0.0022."""
    v = v.strip().rstrip("ΩVAFHzWs").strip()
    m = re.fullmatch(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)([TGMkKmuµnp]?)(\d*)", v)
    if not m:
        raise MathError("bad number: " + v)
    num = m.group(1) + ("." + m.group(3) if m.group(3) else "")
    return float(num) * _PREFIX.get(m.group(2), 1.0)


def eng(x, unit=""):
    """Engineering notation: 0.0047 -> '4.7 m'."""
    if x == 0 or not math.isfinite(x):
        return "%g %s" % (x, unit)
    for p, k in (("T", 1e12), ("G", 1e9), ("M", 1e6), ("k", 1e3), ("", 1), ("m", 1e-3), ("µ", 1e-6), ("n", 1e-9), ("p", 1e-12)):
        if abs(x) >= k:
            return "%.4g %s%s" % (x / k, p, unit)
    return "%.4g %s" % (x, unit)


def kv(args):
    return {k.strip(): v.strip() for k, v in re.findall(r"(\w+)\s*=\s*([^\s,;]+)", args)}


class Professor:
    def __init__(self, lang="en"):
        self.lang = lang

    def L(self, en, pt):
        return pt if self.lang == "pt" else en

    # ---------------------------------------------------------------- dispatch
    def ask(self, text):
        text = text.strip()
        if not text:
            return self.help()
        head, _, rest = text.partition(" ")
        fn = getattr(self, "t_" + head.lower().replace("-", "_"), None)
        if fn:
            return fn(rest.strip())
        for kw, topic in GLOSSARY_INDEX:
            if kw in text.lower():
                return self.t_explain(topic)
        if _LLM:
            return _LLM(PHD_SYSTEM_PROMPT, text)
        try:   # last resort: treat as maths
            return self.t_solve(text) if "=" in text else self.t_simplify(text)
        except Exception:
            return self.help()

    def help(self):
        return self.L(
            "PhD professor topics:\n" + TOPICS_EN, "Tópicos do professor PhD:\n" + TOPICS_EN)

    # ============================================================ mathematics
    def t_solve(self, a):
        expr = parse(a)
        eq = expr if isinstance(expr, sp.Eq) else sp.Eq(expr, 0)
        syms = sorted(eq.free_symbols, key=str)
        sol = sp.solve(eq, syms[0]) if syms else []
        return "%s\n%s: %s = %s" % (self.L("Equation", "Equação") + ": " + sp.sstr(eq), self.L("Solution", "Solução"),
                                   syms[0] if syms else "?", sol)

    def t_simplify(self, a):
        e = parse(a)
        return "%s = %s" % (sp.sstr(e), sp.sstr(sp.simplify(e)))

    def t_diff(self, a):
        e = parse(a); x = _var(e)
        return "d/d%s [%s] = %s" % (x, e, sp.simplify(sp.diff(e, x)))

    def t_integrate(self, a):
        e = parse(a); x = _var(e)
        return "∫ %s d%s = %s + C" % (e, x, sp.integrate(e, x))
    t_int = t_integrate

    def t_limit(self, a):
        expr, _, to = a.partition("->")
        e = parse(expr); x = _var(e)
        p = parse(to) if to.strip() else 0
        return "lim %s->%s %s = %s" % (x, p, e, sp.limit(e, x, p))

    def t_matrix(self, a):
        M = sp.Matrix(parse(a))
        out = ["M = %s" % M.tolist(), "rank = %s" % M.rank()]
        if M.is_square:
            d = M.det()
            out.append("det = %s" % d)
            out.append("trace = %s" % M.trace())
            if d != 0:
                out.append("inv = %s" % M.inv().tolist())
            out.append(self.L("eigenvalues", "autovalores") + " = %s" % M.eigenvals())
            out.append(self.L("Note: det≠0 ⇔ invertible ⇔ full rank.", "Obs.: det≠0 ⇔ inversível ⇔ posto completo."))
        return "\n".join(out)

    def t_ode(self, a):
        """y'' + 3y' + 2y = 0  (y of x by default; use 'y(t)' to pick t)."""
        var = "t" if re.search(r"\by\(t\)|\bt\b", a) else "x"
        s = a.replace("y(%s)" % var, "y")
        s = s.replace("y'''", "D3").replace("y''", "D2").replace("y'", "D1")
        x = sp.Symbol(var); y = sp.Function("y")
        syms = {"D3": y(x).diff(x, 3), "D2": y(x).diff(x, 2), "D1": y(x).diff(x), "y": y(x), var: x}
        e = parse(s, syms)
        eq = e if isinstance(e, sp.Eq) else sp.Eq(e, 0)
        sol = sp.dsolve(eq, y(x))
        return "%s\n%s %s\n%s" % (sp.sstr(eq), self.L("General solution:", "Solução geral:"), sp.sstr(sol),
                                  self.L("Method: characteristic polynomial / undetermined coefficients (sympy dsolve).",
                                         "Método: polinômio característico / coeficientes a determinar (sympy dsolve)."))

    def t_stats(self, a):
        xs = [float(v) for v in re.split(r"[,\s;]+", a.strip()) if v]
        out = ["n = %d" % len(xs), self.L("mean", "média") + " = %.6g" % statistics.mean(xs),
               self.L("median", "mediana") + " = %.6g" % statistics.median(xs)]
        if len(xs) > 1:
            out += [self.L("sample std", "desvio padrão amostral") + " s = %.6g" % statistics.stdev(xs),
                    self.L("population std", "desvio padrão populacional") + " σ = %.6g" % statistics.pstdev(xs),
                    "min/max = %g / %g" % (min(xs), max(xs))]
        return "\n".join(out)

    def t_ncr(self, a):
        n, k = [int(v) for v in re.findall(r"\d+", a)[:2]]
        return "C(%d,%d) = %d   P(%d,%d) = %d   (C = n!/(k!(n-k)!))" % (n, k, math.comb(n, k), n, k, math.perm(n, k))

    def t_gcd(self, a):
        ns = [int(v) for v in re.findall(r"-?\d+", a)]
        g = ns[0]; l = ns[0]
        for v in ns[1:]:
            g = math.gcd(g, v); l = l * v // math.gcd(l, v)
        return "gcd = %d   lcm = %d   (Euclid: gcd(a,b) = gcd(b, a mod b))" % (g, l)

    def t_factor(self, a):
        if re.fullmatch(r"\s*\d+\s*", a):
            return "%s = %s" % (a.strip(), " · ".join("%d^%d" % kv_ if kv_[1] > 1 else str(kv_[0])
                                                    for kv_ in sorted(sp.factorint(int(a)).items())))
        e = parse(a)
        return "%s = %s" % (e, sp.factor(e))

    # ================================================= electrical engineering
    def t_ohm(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        V, I, R = d.get("V"), d.get("I"), d.get("R")
        if V is None and I is not None and R is not None:
            V = I * R; step = "V = I·R = %g·%g" % (I, R)
        elif I is None and V is not None and R is not None:
            I = V / R; step = "I = V/R = %g/%g" % (V, R)
        elif R is None and V is not None and I is not None:
            R = V / I; step = "R = V/I = %g/%g" % (V, I)
        else:
            raise MathError(self.L("give exactly two of V, I, R", "informe exatamente dois de V, I, R"))
        return "%s\nV = %s  I = %s  R = %s  P = V·I = %s" % (step, eng(V, "V"), eng(I, "A"), eng(R, "Ω"), eng(V * I, "W"))

    def t_series(self, a):
        rs = [si(v) for v in re.split(r"[,\s]+", a.strip()) if v]
        return self.L("Series", "Série") + ": R = ΣRi = %s" % eng(sum(rs), "Ω")

    def t_parallel(self, a):
        rs = [si(v) for v in re.split(r"[,\s]+", a.strip()) if v]
        return self.L("Parallel", "Paralelo") + ": 1/R = Σ1/Ri → R = %s" % eng(1 / sum(1 / r for r in rs), "Ω")

    def t_divider(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        vo = d["VIN"] * d["R2"] / (d["R1"] + d["R2"])
        return "Vout = Vin·R2/(R1+R2) = %s" % eng(vo, "V")

    def t_kirchhoff(self, a):
        """kirchhoff V=10 R=1k,2k,3k  -> single-loop KVL: current & drop on each resistor."""
        d = kv(a.replace(" ,", ","))
        V = si(d.get("V", "0"))
        rs = [si(v) for v in re.search(r"R\s*=\s*([^\s]+)", a).group(1).split(",")]
        I = V / sum(rs)
        lines = ["KVL: V - Σ I·Ri = 0  →  I = V/ΣR = %s" % eng(I, "A")]
        lines += ["  V_R%d = %s" % (i + 1, eng(I * r, "V")) for i, r in enumerate(rs)]
        lines.append("KCL: Σ I_in = Σ I_out " + self.L("(same current in a series loop)", "(mesma corrente numa malha série)"))
        return "\n".join(lines)

    def t_impedance(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        R, L, C, f = d.get("R", 0.0), d.get("L", 0.0), d.get("C"), d.get("F", 50.0)
        w = 2 * math.pi * f
        XL = w * L; XC = 1 / (w * C) if C else 0.0
        Z = complex(R, XL - XC)
        out = ["ω = 2πf = %.6g rad/s" % w, "X_L = ωL = %s   X_C = 1/(ωC) = %s" % (eng(XL, "Ω"), eng(XC, "Ω")),
               "Z = R + j(X_L - X_C) = %.6g %+.6gj Ω" % (Z.real, Z.imag),
               "|Z| = %s   ∠Z = %.4g°" % (eng(abs(Z), "Ω"), math.degrees(cmath.phase(Z)))]
        if L and C:
            out.append(self.L("Resonance", "Ressonância") + ": f0 = 1/(2π√(LC)) = %s" % eng(1 / (2 * math.pi * math.sqrt(L * C)), "Hz"))
            if R:
                out.append("Q = (1/R)·√(L/C) = %.4g" % (math.sqrt(L / C) / R))
        if "V" in d:
            I = d["V"] / Z
            out.append("I = V/Z = %s ∠%.4g°   P = |I|²R = %s   S = %s VA   pf = cos φ = %.4g" % (
                eng(abs(I), "A"), math.degrees(cmath.phase(I)), eng(abs(I) ** 2 * R, "W"),
                eng(abs(d["V"] * I), ""), R / abs(Z) if abs(Z) else 1))
        return "\n".join(out)

    def t_rc(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        R, C = d["R"], d["C"]; tau = R * C
        return "\n".join(["τ = RC = %s" % eng(tau, "s"),
                          "f_c = 1/(2πRC) = %s" % eng(1 / (2 * math.pi * tau), "Hz"),
                          self.L("Charging", "Carga") + ": v(t) = V·(1 - e^(-t/τ)); 63.2%% @ τ, 99.3%% @ 5τ = %s" % eng(5 * tau, "s"),
                          "H(s) = 1/(1 + sRC)  (" + self.L("low-pass", "passa-baixa") + ", -20 dB/dec)"])

    def t_rl(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        tau = d["L"] / d["R"]
        return "τ = L/R = %s   f_c = R/(2πL) = %s   i(t) = (V/R)(1 - e^(-t/τ))" % (
            eng(tau, "s"), eng(1 / (2 * math.pi * tau), "Hz"))

    def t_rlc(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        R, L, C = d["R"], d["L"], d["C"]
        w0 = 1 / math.sqrt(L * C); zeta = R / 2 * math.sqrt(C / L)
        kind = (self.L("underdamped", "subamortecido") if zeta < 1 else
                self.L("critically damped", "criticamente amortecido") if zeta == 1 else self.L("overdamped", "superamortecido"))
        return "ω0 = 1/√(LC) = %.6g rad/s (f0 = %s)\nζ = (R/2)√(C/L) = %.4g → %s\nQ = 1/(2ζ) = %.4g" % (
            w0, eng(w0 / (2 * math.pi), "Hz"), zeta, kind, 1 / (2 * zeta) if zeta else float("inf"))

    def t_phasor(self, a):
        m = re.match(r"\s*([-\d.eE+]+)\s*(?:∠|<|@)\s*([-\d.eE+]+)", a)
        if m:
            mag, ang = float(m.group(1)), float(m.group(2))
            z = cmath.rect(mag, math.radians(ang))
            return "%g∠%g° = %.6g %+.6gj   (v(t) = %g·cos(ωt %+g°))" % (mag, ang, z.real, z.imag, mag, ang)
        z = complex(sp.N(parse(a)))
        return "%s = %.6g∠%.6g°" % (a.strip(), abs(z), math.degrees(cmath.phase(z)))

    def t_power(self, a):
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        V, I, pf = d["V"], d["I"], d.get("PF", 1.0)
        S = V * I; P = S * pf; Q = S * math.sin(math.acos(pf))
        return "S = V·I = %s VA\nP = S·pf = %s\nQ = S·sin φ = %s var\n%s" % (
            eng(S), eng(P, "W"), eng(Q), self.L("Power triangle: S² = P² + Q²", "Triângulo de potências: S² = P² + Q²"))

    def t_db(self, a):
        d = kv(a)
        if d:
            k = {k.upper(): si(v) for k, v in d.items()}
            if "P" in k:
                return "dB = 10·log10(P) = %.4g dB" % (10 * math.log10(k["P"]))
            return "dB = 20·log10(V) = %.4g dB" % (20 * math.log10(k["V"]))
        x = si(a)
        return "20·log10(%g) = %.4g dB (amplitude)   10·log10(%g) = %.4g dB (%s)" % (
            x, 20 * math.log10(x), x, 10 * math.log10(x), self.L("power", "potência"))

    def t_filter(self, a):
        """filter lowpass|highpass R=.. C=..  or  bandpass R L C."""
        kind = (a.split() or ["lowpass"])[0].lower()
        d = {k.upper(): si(v) for k, v in kv(a).items()}
        if "L" in d and "C" in d:
            f0 = 1 / (2 * math.pi * math.sqrt(d["L"] * d["C"]))
            bw = d.get("R", 0) / (2 * math.pi * d["L"])
            return "RLC %s: f0 = %s  BW = R/(2πL) = %s" % (kind, eng(f0, "Hz"), eng(bw, "Hz"))
        fc = 1 / (2 * math.pi * d["R"] * d["C"])
        H = "1/(1+sRC)" if kind.startswith("low") else "sRC/(1+sRC)"
        return "RC %s: H(s) = %s  f_c = %s  |H(f_c)| = -3.01 dB, %s" % (
            kind, H, eng(fc, "Hz"), self.L("slope 20 dB/decade", "inclinação 20 dB/década"))

    # =============================================================== computing
    def t_bigo(self, a):
        key = a.lower().strip()
        for k, (cx, why_en, why_pt) in BIGO.items():
            if k in key:
                return "%s: %s\n%s" % (k, cx, self.L(why_en, why_pt))
        return self.L("Known: ", "Conhecidos: ") + ", ".join(BIGO)

    def t_base(self, a):
        s = a.strip().lower()
        n = int(s, 0) if s.startswith(("0x", "0b", "0o")) else int(s)
        return "dec %d = bin %s = oct %s = hex %s   (%s)" % (
            n, bin(n), oct(n), hex(n), self.L("complement-2 8-bit", "complemento de 2 em 8 bits") + ": " + format(n & 0xFF, "08b"))

    def t_bool(self, a):
        e = parse(a.replace("!", "~").replace("&&", "&").replace("||", "|").replace("+", "|"))
        syms = sorted(e.free_symbols, key=str)
        rows = [" ".join(str(s) for s in syms) + " | out"]
        for bits in range(2 ** len(syms)):
            vals = {s: bool((bits >> (len(syms) - 1 - i)) & 1) for i, s in enumerate(syms)}
            rows.append(" ".join(str(int(vals[s])) for s in syms) + " | " + str(int(bool(e.subs(vals)))))
        return "%s\n%s: %s   (SOP)\n%s" % ("\n".join(rows), self.L("Minimal", "Mínima"),
                                          sp.simplify_logic(e, form="dnf"), "CNF: %s" % sp.simplify_logic(e, form="cnf"))

    def t_dfa(self, a):
        """dfa start=q0 accept=q1 q0,0=q0 q0,1=q1 q1,0=q1 q1,1=q0 input=1011"""
        d = dict(re.findall(r"(\w+)=(\w+)", a))
        trans = {(s, c): t for s, c, t in re.findall(r"(\w+),(\w)=(\w+)", a)}
        state = d["start"]; path = [state]
        for ch in d.get("input", ""):
            state = trans.get((state, ch))
            if state is None:
                return self.L("rejected (no transition)", "rejeitada (sem transição)") + " " + "→".join(path)
            path.append(state)
        acc = state in d.get("accept", "").split("|")
        return "%s  %s" % (" → ".join(path), self.L("ACCEPTED", "ACEITA") if acc else self.L("REJECTED", "REJEITADA"))

    # ======================================================== systems analysis
    def t_tf(self, a):
        s = sp.Symbol("s")
        H = sp.together(parse(a, {"s": s}))
        num, den = sp.fraction(H)
        zeros = sp.roots(sp.Poly(num, s)) if num.has(s) else {}
        poles = sp.roots(sp.Poly(den, s))
        stable = all(sp.re(p) < 0 for p in poles)
        marginal = all(sp.re(p) <= 0 for p in poles) and not stable
        out = ["H(s) = %s" % sp.sstr(H), self.L("zeros", "zeros") + ": %s" % list(zeros),
               self.L("poles", "polos") + ": %s" % list(poles),
               self.L("Stability", "Estabilidade") + ": " + (self.L("BIBO stable (all poles in LHP)", "BIBO estável (todos os polos no SPE)") if stable
                                                           else self.L("marginally stable", "marginalmente estável") if marginal
                                                           else self.L("UNSTABLE (pole with Re ≥ 0)", "INSTÁVEL (polo com Re ≥ 0)"))]
        if stable:
            out.append(self.L("DC gain", "Ganho DC") + " H(0) = %s" % sp.nsimplify(H.subs(s, 0)))
        out.append("Bode:")
        for w in (0.1, 1, 10, 100):
            v = complex(sp.N(H.subs(s, sp.I * w)))
            out.append("  ω=%-6g |H|=%8.3f dB  ∠H=%8.2f°" % (w, 20 * math.log10(abs(v)) if abs(v) else -math.inf,
                                                        math.degrees(cmath.phase(v))))
        return "\n".join(out)

    def t_laplace(self, a):
        t, s = sp.symbols("t s", positive=True)
        f = parse(a, {"t": t, "s": s})
        return "L{%s} = %s" % (f, sp.simplify(sp.laplace_transform(f, t, s, noconds=True)))

    def t_ilaplace(self, a):
        t, s = sp.symbols("t s", positive=True)
        F = parse(a, {"t": t, "s": s})
        return "L⁻¹{%s} = %s" % (F, sp.simplify(sp.inverse_laplace_transform(F, s, t)))

    def t_routh(self, a):
        """routh 1 3 3 1  (coefficients of the characteristic polynomial, highest power first)."""
        c = [sp.nsimplify(v) for v in re.split(r"[,\s]+", a.strip()) if v]
        n = len(c)
        rows = [c[0::2], c[1::2] + [0] * (len(c[0::2]) - len(c[1::2]))]
        for _ in range(n - 2):
            r1, r2 = rows[-2], rows[-1]
            if r2[0] == 0:
                r2[0] = sp.Symbol("eps")
            new = [sp.simplify((r2[0] * r1[i + 1] - r1[0] * r2[i + 1]) / r2[0]) for i in range(len(r1) - 1)] + [0]
            rows.append(new)
        col = [r[0] for r in rows[:n]]
        changes = sum(1 for x, y in zip(col, col[1:]) if (sp.sign(x.subs("eps", 1e-9)) != sp.sign(y.subs("eps", 1e-9))))
        table = "\n".join("s^%d | %s" % (n - 1 - i, "  ".join(sp.sstr(v) for v in r)) for i, r in enumerate(rows[:n]))
        return table + "\n" + self.L("sign changes = RHP poles = %d", "trocas de sinal = polos no SPD = %d") % changes

    # ================================================================ concepts
    def t_explain(self, a):
        g = GLOSSARY.get(a.lower().strip())
        if not g:
            return self.L("Concepts: ", "Conceitos: ") + ", ".join(sorted(GLOSSARY))
        return "%s\n%s" % (a.upper(), g[1] if self.lang == "pt" else g[0])


def _var(e):
    syms = sorted(getattr(e, "free_symbols", []), key=str)
    for pref in ("x", "t", "s"):
        for v in syms:
            if str(v) == pref:
                return v
    return syms[0] if syms else sp.Symbol("x")


TOPICS_EN = """  math:    solve, simplify, diff, integrate, limit (expr -> point), matrix, ode, stats, ncr, gcd, factor
  EE:      ohm, series, parallel, divider, kirchhoff, impedance, rc, rl, rlc, phasor, power, db, filter
  CS:      bigo <algorithm>, base <n>, bool <expr>, dfa start=.. accept=.. q0,0=q1 .. input=..
  systems: tf <H(s)>, laplace <f(t)>, ilaplace <F(s)>, routh <coeffs>
  concepts: explain <ohm|kirchhoff|fourier|laplace|eigen|bigo|automata|stability|bayes|...>
  examples: prof ohm V=12 R=4k | prof impedance R=10 L=10m C=100u f=60 | prof tf (s+1)/(s^2+3s+2)"""

BIGO = {
    "binary search": ("O(log n)", "Halves the search interval each step.", "Divide o intervalo pela metade a cada passo."),
    "linear search": ("O(n)", "Inspects each element once.", "Inspeciona cada elemento uma vez."),
    "bubble sort": ("O(n²) worst/avg, O(n) best", "Nested passes swapping neighbours.", "Passadas aninhadas trocando vizinhos."),
    "insertion sort": ("O(n²), O(n) nearly sorted", "Shifts each item into the sorted prefix.", "Insere cada item no prefixo ordenado."),
    "merge sort": ("O(n log n), O(n) memory", "T(n)=2T(n/2)+O(n) → Master theorem case 2.", "T(n)=2T(n/2)+O(n) → Teorema Mestre caso 2."),
    "quick sort": ("O(n log n) avg, O(n²) worst", "Partition around a pivot; bad pivots degrade.", "Particiona em torno do pivô; pivôs ruins degradam."),
    "heap sort": ("O(n log n), O(1) memory", "n extract-max on a binary heap of height log n.", "n extrações num heap binário de altura log n."),
    "hash table": ("O(1) avg, O(n) worst", "Direct addressing via hash; collisions chain.", "Endereçamento por hash; colisões encadeiam."),
    "bfs": ("O(V+E)", "Every vertex and edge visited once with a queue.", "Cada vértice e aresta visitados uma vez com fila."),
    "dfs": ("O(V+E)", "Every vertex and edge visited once with a stack.", "Cada vértice e aresta visitados uma vez com pilha."),
    "dijkstra": ("O((V+E) log V) with binary heap", "Greedy relaxations with a priority queue.", "Relaxações gulosas com fila de prioridade."),
    "fft": ("O(n log n)", "Cooley-Tukey splits the DFT into even/odd halves.", "Cooley-Tukey divide a DFT em pares/ímpares."),
    "matrix multiplication": ("O(n³) naive, O(n^2.81) Strassen", "n² entries × n products each.", "n² entradas × n produtos cada."),
    "fibonacci": ("O(2ⁿ) naive, O(n) DP, O(log n) matrix power", "Memoisation removes overlapping subproblems.", "Memoização remove subproblemas sobrepostos."),
    "bst": ("O(log n) balanced, O(n) degenerate", "Height bounds every operation.", "A altura limita cada operação."),
}

GLOSSARY = {
    "ohm": ("V = R·I. Linear resistors: current proportional to voltage.", "V = R·I. Resistores lineares: corrente proporcional à tensão."),
    "kirchhoff": ("KCL: Σ currents into a node = 0 (charge conservation). KVL: Σ voltages around a loop = 0 (energy conservation).",
                  "LCK: Σ correntes num nó = 0 (conservação de carga). LTK: Σ tensões numa malha = 0 (conservação de energia)."),
    "fourier": ("Any periodic signal = sum of sinusoids; X(f) = ∫ x(t) e^(-j2πft) dt.", "Todo sinal periódico = soma de senoides; X(f) = ∫ x(t) e^(-j2πft) dt."),
    "laplace": ("F(s) = ∫₀^∞ f(t) e^(-st) dt turns ODEs into algebra; s = σ + jω.", "F(s) = ∫₀^∞ f(t) e^(-st) dt transforma EDOs em álgebra; s = σ + jω."),
    "eigen": ("Av = λv: directions A only scales. λ from det(A - λI) = 0.", "Av = λv: direções que A apenas escala. λ de det(A - λI) = 0."),
    "bigo": ("f = O(g) if f(n) ≤ c·g(n) for n ≥ n0: asymptotic upper bound.", "f = O(g) se f(n) ≤ c·g(n) para n ≥ n0: limite superior assintótico."),
    "automata": ("DFA (Q, Σ, δ, q0, F) recognises regular languages; PDA adds a stack (context-free); Turing machine = general computation.",
                 "AFD (Q, Σ, δ, q0, F) reconhece linguagens regulares; AP adiciona pilha (livres de contexto); máquina de Turing = computação geral."),
    "stability": ("LTI system is BIBO stable iff all poles have Re(p) < 0 (continuous) or |p| < 1 (discrete).",
                  "Sistema LTI é BIBO estável sse todos os polos têm Re(p) < 0 (contínuo) ou |p| < 1 (discreto)."),
    "bayes": ("P(A|B) = P(B|A)·P(A)/P(B).", "P(A|B) = P(B|A)·P(A)/P(B)."),
    "derivative": ("f'(x) = lim h→0 (f(x+h) - f(x))/h: instantaneous rate of change.", "f'(x) = lim h→0 (f(x+h) - f(x))/h: taxa de variação instantânea."),
    "integral": ("∫ₐᵇ f dx = F(b) - F(a) (fundamental theorem of calculus).", "∫ₐᵇ f dx = F(b) - F(a) (teorema fundamental do cálculo)."),
    "impedance": ("Z = R + jX; Z_L = jωL, Z_C = 1/(jωC). Ohm's law in phasors: V = Z·I.", "Z = R + jX; Z_L = jωL, Z_C = 1/(jωC). Lei de Ohm fasorial: V = Z·I."),
    "decibel": ("dB = 10 log10(P2/P1) = 20 log10(V2/V1). +3 dB ≈ 2× power, +6 dB ≈ 2× voltage.",
                "dB = 10 log10(P2/P1) = 20 log10(V2/V1). +3 dB ≈ 2× potência, +6 dB ≈ 2× tensão."),
    "recursion": ("Solve by reducing to smaller instances; analyse with recurrences / Master theorem.", "Resolver reduzindo a instâncias menores; analisar com recorrências / Teorema Mestre."),
    "solid": ("SRP, Open/Closed, Liskov, Interface segregation, Dependency inversion.", "SRP, Aberto/Fechado, Liskov, Segregação de interface, Inversão de dependência."),
}
GLOSSARY_INDEX = [(k, k) for k in GLOSSARY] + [("lei de ohm", "ohm"), ("autovalor", "eigen"), ("estabilidade", "stability"),
                                              ("autômato", "automata"), ("derivada", "derivative"), ("complexidade", "bigo")]
