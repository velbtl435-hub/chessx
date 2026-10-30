import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.mathx import dispatch, parse, MathError, Professor
from chessx_libs.mathx.professor import si


class TestCore(unittest.TestCase):
    def test_parse_implicit(self):
        self.assertEqual(str(parse("2x^2 + 3(x+1)")), "2*x**2 + 3*x + 3")

    def test_sci_notation(self):
        self.assertEqual(float(parse("2e3")), 2000.0)

    def test_rejects_unsafe(self):
        for bad in ("__import__('os')", "x.__class__", "(lambda: 1)()", "open('f')" * 0 + "a[0]"):
            with self.assertRaises(MathError):
                parse(bad)

    def test_huge_pow(self):
        with self.assertRaises(MathError):
            parse("9**99999999")


class TestProfessor(unittest.TestCase):
    def setUp(self):
        self.p = Professor("en")

    def test_si(self):
        self.assertAlmostEqual(si("4k7"), 4700)
        self.assertAlmostEqual(si("100u"), 1e-4)

    def test_ohm(self):
        self.assertIn("I = 3 mA", self.p.ask("ohm V=12 R=4k"))

    def test_parallel(self):
        self.assertIn("50 Ω", self.p.ask("parallel 100 100"))

    def test_impedance_resonance(self):
        self.assertIn("159.2 Hz", self.p.ask("impedance R=10 L=10m C=100u f=60"))

    def test_rlc(self):
        self.assertIn("underdamped", self.p.ask("rlc R=10 L=1m C=1u"))

    def test_tf(self):
        out = self.p.ask("tf (s+1)/(s^2+3s+2)")
        self.assertIn("BIBO stable", out)
        self.assertIn("1/2", out)

    def test_tf_unstable(self):
        self.assertIn("UNSTABLE", self.p.ask("tf 1/(s^2 - 1)"))

    def test_routh(self):
        self.assertIn("= 2", self.p.ask("routh 1 2 3 10"))

    def test_laplace(self):
        self.assertIn("1/(s + 2)", self.p.ask("laplace exp(-2t)"))

    def test_ode(self):
        self.assertIn("exp(-x)", self.p.ask("ode y''+3y'+2y=0"))

    def test_bool(self):
        self.assertIn("Minimal: A", self.p.ask("bool A&B | A&~B"))

    def test_dfa(self):
        self.assertIn("ACCEPTED", self.p.ask("dfa start=q0 accept=q0 q0,1=q1 q1,1=q0 input=11"))

    def test_bigo(self):
        self.assertIn("O(log n)", self.p.ask("bigo binary search"))

    def test_matrix(self):
        self.assertIn("det = -2", self.p.ask("matrix [[1,2],[3,4]]"))

    def test_stats(self):
        self.assertIn("mean = 2.5", self.p.ask("stats 1 2 3 4"))

    def test_pt(self):
        self.assertIn("Solução", Professor("pt").ask("solve x^2-4=0"))

    def test_glossary_fallback(self):
        self.assertIn("KCL", self.p.ask("what is kirchhoff law?"))

    def test_dispatch(self):
        self.assertIn("x = [2]", dispatch("math 2x+3=7"))
        self.assertTrue(dispatch("math __import__('os')").startswith("math error"))


if __name__ == "__main__":
    unittest.main()
