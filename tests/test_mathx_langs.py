import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chessx_libs.mathx import dispatch, MathError
from chessx_libs.mathx.langs import export, translate, safe_eval, from_notation


class TestLangs(unittest.TestCase):
    def test_exports(self):
        e = "sqrt(x^2+1)/(2pi) + exp(-x)"
        self.assertIn("x.^2", export(e, "matlab"))
        self.assertIn("numpy.sqrt", export(e, "numpy"))
        self.assertIn("\\frac", export(e, "latex"))
        self.assertIn("Exp[-x]", export(e, "wolfram"))
        self.assertIn("M_PI", export(e, "c"))
        self.assertIn("x .^ 2", export(e, "julia"))
        self.assertIn("sqrt(x^2 + 1)", export(e, "r"))

    def test_matrix_export(self):
        self.assertIn("byrow=TRUE", export("[[1,2],[3,4]]", "r"))
        self.assertEqual(export("[[1,2],[3,4]]", "c"), "{{1, 2}, {3, 4}}")

    def test_translate(self):
        self.assertEqual(translate("Sin[x]^2 + Sqrt[x]", "wolfram", "python"), "math.sqrt(x) + math.sin(x)**2")
        self.assertIn("pow(x, 2)/sqrt(y)", translate(r"\frac{x^{2}}{\sqrt{y}}", "latex", "c"))
        self.assertEqual(str(from_notation("[1 2; 3 4]", "matlab")), "[[1, 2], [3, 4]]")
        self.assertEqual(translate("pow(x,2)+M_PI", "c", "wolfram"), "x^2 + Pi")

    def test_safe_eval(self):
        out = safe_eval("a = 3; b = a^2 + 1; sqrt(b)")
        self.assertEqual(out[1], "b = 10")
        self.assertIn("3.16227766", out[2])

    def test_sandbox_blocks(self):
        for bad in ('__import__("os")', "a.b", "x[0]", "(lambda: 1)()", "2**99999999", "[i for i in x]", "_x = 1"):
            with self.assertRaises(MathError, msg=bad):
                safe_eval(bad)

    def test_commands(self):
        self.assertIn("latex:", dispatch("export all x^2/2"))
        self.assertIn("[-2, 2]", dispatch("export python solve x^2 - 4 = 0"))
        self.assertIn("math.sin", dispatch("translate matlab python sin(x).^2"))
        self.assertIn("b = 10", dispatch("calc", read_block=lambda: ["a = 3", "b = a^2 + 1"]))


if __name__ == "__main__":
    unittest.main()
